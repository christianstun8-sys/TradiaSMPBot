import discord
from discord.ext import commands
from pymongo import MongoClient
import concurrent.futures
from typing import Optional
import os
import dotenv

dotenv.load_dotenv()


MODMAIL_CATEGORY_ID = 1447666165584494774
CLOSED_MODMAIL_CATEGORY_ID = 1447666069736128542
SUPPORT_GUILD_ID = 1424501227521314979
DB_NAME = "serverdata"
COLLECTION_NAME = "modmail"
# -----------------------------

class ModMail(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        mongo_uri = os.getenv('MONGO_URI')

        self.db_client = MongoClient(mongo_uri)
        self.db = self.db_client[DB_NAME]
        self.collection = self.db[COLLECTION_NAME]

        self.bot.loop.create_task(self._create_index())

    def _sync_create_index(self):
        try:
            self.collection.create_index("user_id", unique=True)
            print("MongoDB Index für ModMail erstellt/bestätigt.")
        except Exception as e:
            print(f"Fehler beim Erstellen des MongoDB Index: {e}")

    async def _create_index(self):
        await self.bot.loop.run_in_executor(self._executor, self._sync_create_index)

    def _sync_get_modmail(self, user_id: int) -> Optional[dict]:
        return self.collection.find_one({"user_id": user_id, "type": "modmail"})

    async def get_modmail(self, user_id: int) -> Optional[dict]:
        return await self.bot.loop.run_in_executor(self._executor, self._sync_get_modmail, user_id)

    def _sync_create_modmail(self, user_id: int, post_id: int):
        self.collection.insert_one({
            "user_id": user_id,
            "post_id": post_id,
            "type": "modmail"
        })

    async def create_modmail(self, user_id: int, post_id: int):
        await self.bot.loop.run_in_executor(self._executor, self._sync_create_modmail, user_id, post_id)

    def _sync_delete_modmail(self, user_id: int):
        self.collection.delete_one({"user_id": user_id})

    async def delete_modmail(self, user_id: int):
        await self.bot.loop.run_in_executor(self._executor, self._sync_delete_modmail, user_id)

    @commands.command(name="c-modmail")
    async def open_modmail_case(self, ctx: commands.Context):
        if ctx.guild is not None:
            await ctx.send("Diesen Befehl kannst du nur per Direktnachricht (DM) an mich verwenden, um eine Anfrage zu starten!")
            return

        user_id = ctx.author.id

        if await self.get_modmail(user_id):
            await ctx.send("Du hast bereits einen **offenen** Modmail-Fall. Sende einfach deine Nachricht, um fortzufahren.")
            return

        support_guild = self.bot.get_guild(SUPPORT_GUILD_ID)
        if support_guild is None:
            await ctx.send("Ein interner Fehler ist aufgetreten (Server nicht gefunden).")
            return

        category = support_guild.get_channel(MODMAIL_CATEGORY_ID)
        if category is None or not isinstance(category, discord.CategoryChannel):
            await ctx.send("Ein interner Fehler ist aufgetreten (Kategorie für offene Fälle nicht gefunden).")
            return

        try:
            display_name = str(ctx.author.display_name).lower().replace(' ', '-')
            channel_name = f"open-{display_name[:50]}-{ctx.author.id}"

            new_channel = await support_guild.create_text_channel(
                name=channel_name,
                category=category,
                topic=f"Modmail-Support von {ctx.author.name}#{ctx.author.discriminator} ({ctx.author.id})."
            )
        except Exception:
            await ctx.send("Konnte den Kanal auf dem Server nicht erstellen. Bitte wende dich an die Administration.")
            return

        await self.create_modmail(user_id, new_channel.id)

        await new_channel.send(
            f"**Neuer Modmail-Fall** von {ctx.author.mention} (`{ctx.author.id}`).\n"
            f"Der Nutzer wurde benachrichtigt und kann nun per DM antworten."
        )

        embed = discord.Embed(
            title="✅ Modmail-Anfrage erfolgreich erstellt",
            description="Dein Supportfall wurde geöffnet. Du kannst nun einfach per DM antworten. Deine Nachrichten werden an das Team weitergeleitet. Um den Chat zu schließen, nutze `t!del-modmail`.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Sende eine Nachricht, um zu antworten!")
        await ctx.send(embed=embed)


    @commands.command(name="del-modmail")
    async def close_modmail_case(self, ctx: commands.Context):

        user_id_to_delete = None

        if ctx.guild is None:
            mail_case = await self.get_modmail(ctx.author.id)
            if not mail_case:
                await ctx.send("Du hast keinen **offenen** Modmail-Fall, den ich schließen könnte.")
                return

            user_id_to_delete = ctx.author.id
            channel_id = mail_case['post_id']
            channel = self.bot.get_channel(channel_id)
            user_display_name = str(ctx.author.display_name).lower().replace(' ', '-')

        else:
            support_guild = self.bot.get_guild(SUPPORT_GUILD_ID)
            if support_guild is None or ctx.guild.id != SUPPORT_GUILD_ID:
                await ctx.send("Dieser Befehl kann nur auf dem Support-Server oder in DMs ausgeführt werden.")
                return

            channel_parts = ctx.channel.name.split('-')

            try:
                if len(channel_parts) < 3:
                    await ctx.send("Dieser Kanal scheint kein offener Modmail-Kanal zu sein (Name passt nicht).")
                    return

                user_id_to_delete = int(channel_parts[-1])
            except ValueError:
                await ctx.send("Konnte die User-ID nicht aus dem Kanalnamen extrahieren.")
                return

            mail_case = await self.get_modmail(user_id_to_delete)
            if not mail_case:
                await ctx.send("Dieser Modmail-Fall scheint bereits geschlossen zu sein (nicht in der DB gefunden).")
                await ctx.channel.edit(name=f"deleted-{ctx.channel.name}")
                return

            channel = ctx.channel
            user = self.bot.get_user(user_id_to_delete)
            user_display_name = str(user.display_name).lower().replace(' ', '-') if user else "deleted-user"


        await self.delete_modmail(user_id_to_delete)

        # NEUER CODE-ABSCHNITT FÜR KATEGORIE-VERSCHIEBUNG UND UMBENENNUNG
        # Den Kanal umbenennen (zu 'deleted-...')
        new_channel_name = f"deleted-{user_display_name}-{user_id_to_delete}"[:100]
        closed_category = self.bot.get_channel(CLOSED_MODMAIL_CATEGORY_ID)

        try:
            edit_kwargs = {"name": new_channel_name}

            if closed_category and isinstance(closed_category, discord.CategoryChannel):
                # Wenn die geschlossene Kategorie gefunden wurde, den Kanal verschieben
                edit_kwargs["category"] = closed_category

            await channel.edit(**edit_kwargs)

        except Exception:
            # Fehler beim Verschieben/Umbenennen
            pass
            # ENDE NEUER CODE-ABSCHNITT

        user_to_notify = self.bot.get_user(user_id_to_delete)
        if user_to_notify:
            try:
                embed = discord.Embed(
                    title="❌ Modmail-Anfrage geschlossen",
                    description="Dein Modmail-Fall wurde geschlossen. Du kannst keine weiteren Nachrichten über diesen Fall senden oder empfangen.",
                    color=discord.Color.red()
                )
                await user_to_notify.send(embed=embed)
            except:
                pass

        final_message = f"✅ Modmail-Fall für User **{user_id_to_delete}** wurde geschlossen. Der Kanal wurde in die `deleted-` Kategorie verschoben und umbenannt."
        if ctx.guild:
            await ctx.send(final_message)


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author.bot:
            return

        if message.content.startswith(self.bot.command_prefix):
            if message.guild is None and message.content.startswith("t!c-modmail"):
                return
            if message.guild is None and message.content.startswith("t!del-modmail"):
                return

        if message.guild is None:
            user_id = message.author.id
            mail_case = await self.get_modmail(user_id)

            if not mail_case:
                if not message.content.startswith("!"):
                    await message.channel.send("Du hast keinen **offenen** Modmail-Fall. Bitte benutze `t!c-modmail <Nachricht>`, um eine neue Supportanfrage zu starten.")
                return

            post_channel = self.bot.get_channel(mail_case['post_id'])

            if post_channel is None:
                await self.delete_modmail(user_id)
                await message.channel.send("Fehler: Dein Modmail-Kanal auf dem Server wurde nicht gefunden. Dein Fall wurde geschlossen. Starte ihn neu mit `t!c-modmail`.")
                return

            embed = discord.Embed(
                title=f"Neue Nachricht von {message.author.display_name}",
                description=message.content,
                color=discord.Color.blue()
            )
            embed.set_author(name=f"User ID: {user_id}", icon_url=message.author.display_avatar.url)

            if message.attachments:
                attachments_list = "\n".join([f"[{att.filename}]({att.url})" for att in message.attachments])
                embed.add_field(name="Anhänge", value=attachments_list, inline=False)
                if message.attachments[0].content_type in ('image/png', 'image/jpeg', 'image/gif'):
                    embed.set_image(url=message.attachments[0].url)

            await post_channel.send(embed=embed)

            await message.add_reaction("✅")
            return

        else:
            if message.guild.id != SUPPORT_GUILD_ID:
                return

            if not message.channel.name.startswith("open-"):
                return

            try:
                user_id = int(message.channel.name.split('-')[-1])
            except ValueError:
                return

            mail_case = await self.get_modmail(user_id)
            if not mail_case:
                return

            user_to_send = self.bot.get_user(user_id)
            if user_to_send is None:
                await message.channel.send("⚠️ Konnte den User nicht finden. Der Fall kann nicht beantwortet werden.")
                return

            embed = discord.Embed(
                title=f"Antwort auf deine Anfrage",
                description=message.content,
                color=discord.Color.gold()
            )
            embed.set_author(
                name=f"Team-Antwort von {message.author.display_name}",
                icon_url=message.author.display_avatar.url
            )
            embed.set_footer(text="Sende eine Nachricht, indem du sie an mich DM'st!")

            try:
                await user_to_send.send(embed=embed)
                await message.add_reaction("✔️")
            except discord.Forbidden:
                await message.channel.send("❌ Konnte die DM nicht an den User senden (wahrscheinlich DMs deaktiviert).")
            except Exception as e:
                await message.channel.send(f"❌ Fehler beim Senden der DM: {e}")


async def setup(bot):
    await bot.add_cog(ModMail(bot))