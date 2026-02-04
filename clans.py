import discord
from discord.ext import commands
from discord import ui
import motor.motor_asyncio as motor
import time
import re
import os
import dotenv

dotenv.load_dotenv()

MONGODB_URI = os.getenv("MONGO_URI")
DB_NAME = "serverdata"
CLAN_SETTINGS_COLLECTION = "clansettings"
CLAN_MEMBERS_COLLECTION = "clanmembers"

ADMIN_CHANNEL_ID = 1450524445541142580
CLAN_PARENT_CATEGORY_ID = 1451266582818062348

HEX_COLOR_REGEX = r"^#[0-9A-Fa-f]{6}$"

class ClanDB:
    def __init__(self):
        self.client = motor.AsyncIOMotorClient(MONGODB_URI)
        self.db = self.client[DB_NAME]
        self.settings = self.db[CLAN_SETTINGS_COLLECTION]
        self.members = self.db[CLAN_MEMBERS_COLLECTION]

    async def get_clan(self, clan_tag=None, owner_id=None):
        query = {}
        if clan_tag:
            query["tag"] = clan_tag
        if owner_id:
            query["owner_id"] = owner_id
        return await self.settings.find_one(query)

    async def get_user_clan(self, user_id: int):
        return await self.members.find_one({"members": user_id})

    async def is_owner(self, user_id: int):
        return await self.settings.find_one({"owner_id": user_id}) is not None

    async def delete_clan(self, clan_tag: str):
        await self.settings.delete_one({"tag": clan_tag})
        await self.members.delete_one({"tag": clan_tag})




    async def add_member(self, clan_tag, user_id):
        await self.members.update_one(
            {"tag": clan_tag},
            {"$addToSet": {"members": user_id}},
            upsert=True
        )

    async def remove_member(self, clan_tag, user_id):
        await self.members.update_one(
            {"tag": clan_tag},
            {"$pull": {"members": user_id}}
        )

    async def insert_clan(self, data):
        await self.settings.insert_one(data)

    async def update_clan(self, owner_id, data):
        await self.settings.update_one({"owner_id": owner_id}, {"$set": data})

    async def get_all_accepted(self):
        return await self.settings.find({"accepted": True}).to_list(None)

class ClanCreationModal(ui.Modal, title="⚔️ Clan erstellen"):
    def __init__(self, db: ClanDB):
        super().__init__()
        self.db = db

    name = ui.TextInput(label="Clanname", placeholder="z.B. Die Nordkrieger")
    tag = ui.TextInput(label="Clan-Tag (max. 5)", max_length=5, placeholder="z.B. NORD")
    color = ui.TextInput(label="Clanfarbe (HEX)", placeholder="#RRGGBB")
    desc = ui.TextInput(label="Clanbeschreibung", style=discord.TextStyle.paragraph)
    approval = ui.TextInput(
        label="Privater Clan?",
        placeholder="Beitritt muss genehmigt werden? (Ja/Nein)",
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not re.fullmatch(HEX_COLOR_REGEX, self.color.value):
            return await interaction.response.send_message(
                "❌ **Ungültiger Farbcode**\nBitte nutze das Format `#RRGGBB`.",
                ephemeral=True
            )

        approval_raw = self.approval.value.lower()
        if approval_raw not in ("ja", "nein"):
            return await interaction.response.send_message(
                "❌ **Ungültige Eingabe**\nBitte antworte nur mit **Ja** oder **Nein**.",
                ephemeral=True
            )

        tag = self.tag.value.upper()

        if await self.db.get_clan(clan_tag=tag):
            return await interaction.response.send_message(
                f"❌ Der Clan-Tag **{tag}** ist bereits vergeben.",
                ephemeral=True
            )

        data = {
            "name": self.name.value,
            "tag": tag,
            "color": self.color.value,
            "desc": self.desc.value,
            "approval_required": approval_raw == "ja",
            "owner_id": interaction.user.id,
            "created": time.time(),
            "accepted": False
        }

        await self.db.insert_clan(data)

        embed = discord.Embed(
            title="📥 Neuer Clan-Antrag",
            description=f"**{data['name']} [{tag}]**",
            color=discord.Color.orange()
        )
        embed.add_field(name="👑 Gründer", value=interaction.user.mention)
        embed.add_field(name="📝 Beschreibung", value=data["desc"], inline=False)
        embed.add_field(
            name="🔒 Beitritt",
            value="Genehmigung erforderlich" if data["approval_required"] else "Offen",
            inline=False
        )

        admin_channel = interaction.guild.get_channel(ADMIN_CHANNEL_ID)
        await admin_channel.send(embed=embed, view=ClanApprovalView(self.db, tag))

        await interaction.response.send_message(
            "✅ **Dein Clan-Antrag wurde eingereicht!**\nEin Server-Admin wird ihn in Kürze prüfen.",
            ephemeral=True
        )

class ClanEditModal(ui.Modal):
    def __init__(self, db: ClanDB, clan: dict, key: str, label: str):
        super().__init__(title=f"{label} bearbeiten")
        self.db = db
        self.clan = clan
        self.key = key

        current = clan.get(key, "")
        if key == "approval_required":
            current = "Ja" if current else "Nein"

        self.input = ui.TextInput(
            label=label,
            default=str(current),
            placeholder="Ja oder Nein" if key == "approval_required" else ""
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.input.value.strip()

        if self.key == "color" and not re.fullmatch(HEX_COLOR_REGEX, value):
            return await interaction.response.send_message(
                "❌ **Ungültiger HEX-Code** (`#RRGGBB`)",
                ephemeral=True
            )

        if self.key == "approval_required":
            if value.lower() not in ("ja", "nein"):
                return await interaction.response.send_message(
                    "❌ Bitte nur **Ja** oder **Nein** eingeben.",
                    ephemeral=True
                )
            value = value.lower() == "ja"

        await self.db.update_clan(
            self.clan["owner_id"],
            {self.key: value}
        )

        await interaction.response.send_message(
            "✅ **Änderung erfolgreich gespeichert.**",
            ephemeral=True
        )

class ClanEditView(ui.View):
    def __init__(self, db: ClanDB, clan: dict):
        super().__init__(timeout=None)
        self.db = db
        self.clan = clan

        fields = {
            "name": "Clanname",
            "color": "Clanfarbe",
            "desc": "Beschreibung",
            "approval_required": "Zustimmung"
        }

        for key, label in fields.items():
            button = ui.Button(label=f"{label} ändern", style=discord.ButtonStyle.secondary)
            button.callback = self.make_callback(key, label)
            self.add_item(button)

        delete_button = ui.Button(
            label="🗑️ Clan löschen",
            style=discord.ButtonStyle.danger
        )
        delete_button.callback = self.request_delete
        self.add_item(delete_button)

    async def ensure_owner(self, interaction: discord.Interaction) -> bool:
        clan = await self.db.get_clan(owner_id=interaction.user.id)
        if not clan:
            await interaction.response.send_message(
                "❌ **Nur der Clan-Owner darf dieses Panel benutzen.**",
                ephemeral=True
            )
            return False
        return True

    def make_callback(self, key, label):
        async def callback(interaction: discord.Interaction):
            if not await self.ensure_owner(interaction):
                return

            latest = await self.db.get_clan(owner_id=interaction.user.id)
            await interaction.response.send_modal(
                ClanEditModal(self.db, latest, key, label)
            )
        return callback

    async def request_delete(self, interaction: discord.Interaction):
        if not await self.ensure_owner(interaction):
            return

        await interaction.response.edit_message(
            content="⚠️ **Willst du den Clan wirklich endgültig löschen?**",
            view=ConfirmDeleteView(self)
        )

    async def final_delete(self, interaction: discord.Interaction):
        clan = await self.db.get_clan(owner_id=interaction.user.id)
        if not clan:
            return

        guild = interaction.guild

        admin_role = guild.get_role(clan.get("admin_role_id"))
        member_role = guild.get_role(clan.get("member_role_id"))
        category = guild.get_channel(clan.get("category_id"))

        if category:
            for channel in list(category.channels):
                await channel.delete()
            await category.delete()

        if admin_role:
            await admin_role.delete()

        if member_role:
            await member_role.delete()

        await self.db.delete_clan(clan["tag"])

        await interaction.response.edit_message(
            content="🗑️ **Der Clan wurde vollständig gelöscht.**",
            view=None
        )

class ConfirmDeleteView(ui.View):
    def __init__(self, parent_view):
        super().__init__(timeout=30)
        self.parent_view = parent_view

    @ui.button(label="❌ Abbrechen", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content="❎ **Löschen abgebrochen.**",
            view=self.parent_view
        )

    @ui.button(label="🗑️ Endgültig löschen", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        await self.parent_view.final_delete(interaction)


class ClanApprovalView(ui.View):
    def __init__(self, db: ClanDB, tag: str):
        super().__init__(timeout=None)
        self.db = db
        self.tag = tag

    @ui.button(label="✅ Akzeptieren", style=discord.ButtonStyle.green, custom_id="clan:approval")
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        clan = await self.db.get_clan(clan_tag=self.tag)
        guild = interaction.guild

        admin_role = await guild.create_role(
            name=f"{self.tag}-Admin",
            color=discord.Color.from_str(clan["color"])
        )
        member_role = await guild.create_role(name=f"{self.tag}-Member")

        parent = guild.get_channel(CLAN_PARENT_CATEGORY_ID)

        category = await guild.create_category(
            name=f"Clan-{self.tag}",
            reason=f"Clan {self.tag} erstellt"
        )

        if parent:
            await category.edit(position=parent.position + 1)



        await category.set_permissions(guild.default_role, read_messages=False)
        await category.set_permissions(admin_role, read_messages=True, manage_channels=True)
        await category.set_permissions(member_role, read_messages=True)

        main_channel = await category.create_text_channel("💬-chat")
        await category.create_voice_channel("🔊 Voice")

        owner = guild.get_member(clan["owner_id"])
        await owner.add_roles(admin_role, member_role)

        await self.db.update_clan(clan["owner_id"], {
            "accepted": True,
            "admin_role_id": admin_role.id,
            "member_role_id": member_role.id,
            "category_id": category.id,
            "main_channel_id": main_channel.id
        })

        await self.db.add_member(self.tag, clan["owner_id"])

        await interaction.message.edit(
            content=f"✅ **Clan `{self.tag}` wurde erfolgreich erstellt.**",
            embed=None,
            view=None
        )

        embed = discord.Embed(
            title="✅ Clan akzeptiert",
            description="Herzlichen Glückwunsch: dein Clan wurde akzeptiert!\n"
                        "Auf dem Server wurde eine Kategorie mit einem Text- und Sprachkanal erstellt.\n"
                        "Bei Problemen melde dich bitte an den Support von TradiaSMP. Vielen Dank!",
            color=discord.Color.green()
        )
        try:
            await owner.send(embed=embed, content=owner.mention)
        except discord.Forbidden:
            pass


class JoinRequestView(ui.View):
    def __init__(self, db: ClanDB, clan_tag: str, user_id: int):
        super().__init__(timeout=86400)
        self.db = db
        self.clan_tag = clan_tag
        self.user_id = user_id

    @ui.button(label="✅ Annehmen", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: ui.Button):
        clan = await self.db.get_clan(clan_tag=self.clan_tag)
        member = interaction.guild.get_member(self.user_id)
        role = interaction.guild.get_role(clan["member_role_id"])

        await member.add_roles(role)
        await self.db.add_member(self.clan_tag, self.user_id)

        await interaction.message.edit(
            content=f"🎉 **{member.mention} wurde in den Clan aufgenommen!**",
            view=None
        )

    @ui.button(label="❌ Ablehnen", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.message.edit(
            content="❌ **Die Beitrittsanfrage wurde abgelehnt.**",
            view=None
        )

class ClanJoinView(ui.View):
    def __init__(self, db: ClanDB, clans):
        super().__init__(timeout=300)
        self.db = db
        self.clans = clans
        self.index = 0

    def embed(self):
        c = self.clans[self.index]
        return discord.Embed(
            title=f"⚔️ {c['name']} [{c['tag']}]",
            description=c["desc"],
            color=discord.Color.from_str(c["color"])
        )

    async def update(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=self.embed(),
            view=self
        )

    @ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        if not self.clans:
            return
        self.index = (self.index - 1) % len(self.clans)
        await self.update(interaction)

    @ui.button(label="🤝 Clan beitreten", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: ui.Button):

        clans = await self.db.get_all_accepted()
        if not clans:
            return await interaction.response.send_message("ℹ️ Es gibt bisher keine Clans zum Beitreten.", ephemeral=True)

        if await self.db.get_user_clan(interaction.user.id):
            return await interaction.response.send_message(
                "❌ **Du bist bereits Mitglied eines Clans.**",
                ephemeral=True
            )

        clan = self.clans[self.index]

        if clan["approval_required"]:
            channel = interaction.guild.get_channel(clan["main_channel_id"])
            if channel:
                embed = discord.Embed(
                    title="📨 Neue Beitrittsanfrage",
                    description=f"{interaction.user.mention} möchte dem Clan beitreten.",
                    color=discord.Color.blue()
                )
                await channel.send(
                    embed=embed,
                    view=JoinRequestView(self.db, clan["tag"], interaction.user.id)
                )

            return await interaction.response.send_message(
                "⏳ **Deine Beitrittsanfrage wurde gesendet.**\nBitte warte auf eine Entscheidung der Clan-Leitung.",
                ephemeral=True
            )
        role = interaction.guild.get_role(clan["member_role_id"])
        if role:
            await interaction.user.add_roles(role)

        await self.db.add_member(clan["tag"], interaction.user.id)

        await interaction.response.send_message(
            f"🎉 **Willkommen im Clan `{clan['name']}`!**",
            ephemeral=True
        )

    @ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def forward(self, interaction: discord.Interaction, button: ui.Button):
        if not self.clans:
            return
        self.index = (self.index + 1) % len(self.clans)
        await self.update(interaction)

class ClanMainView(ui.View):
    def __init__(self, db: ClanDB):
        super().__init__(timeout=None)
        self.db = db

    @ui.button(label="✏️ Clan erstellen", style=discord.ButtonStyle.primary, custom_id="clan:create")
    async def create(self, interaction: discord.Interaction, button: ui.Button):
        if await self.db.get_user_clan(interaction.user.id):
            return await interaction.response.send_message(
                "❌ **Du bist bereits Mitglied eines Clans.**",
                ephemeral=True
            )
        await interaction.response.send_modal(ClanCreationModal(self.db))

@ui.button(label="🤝 Clan beitreten", style=discord.ButtonStyle.secondary, custom_id="clan:join")
async def join(self, interaction: discord.Interaction, button: ui.Button):
    clans = await self.db.get_all_accepted()

    if not clans:
        return await interaction.response.send_message(
            "ℹ️ **Es gibt derzeit keine aktiven Clans zum Beitreten.**",
            ephemeral=True
        )

    if await self.db.get_user_clan(interaction.user.id):
        return await interaction.response.send_message(
            "❌ **Du bist bereits Mitglied eines Clans.**",
            ephemeral=True
        )

    view = ClanJoinView(self.db, clans)
    await interaction.response.send_message(
        embed=view.embed(),
        view=view,
        ephemeral=True
    )

    @ui.button(label="🚪 Clan verlassen", style=discord.ButtonStyle.danger, custom_id="clan:leave")
    async def leave(self, interaction: discord.Interaction, button: ui.Button):
        clan = await self.db.get_user_clan(interaction.user.id)
        if not clan:
            return await interaction.response.send_message(
                "ℹ️ **Du bist aktuell in keinem Clan.**",
                ephemeral=True
            )

        if await self.db.is_owner(interaction.user.id):
            return await interaction.response.send_message(
                "👑 **Clan-Owner können den Clan nicht verlassen.**\nBitte wende dich an den Support.",
                ephemeral=True
            )

        data = await self.db.get_clan(clan_tag=clan["tag"])
        role = interaction.guild.get_role(data["member_role_id"])
        await interaction.user.remove_roles(role)
        await self.db.remove_member(clan["tag"], interaction.user.id)

        await interaction.response.send_message(
            "✅ **Du hast den Clan erfolgreich verlassen.**",
            ephemeral=True
        )

    @ui.button(label="⚙️ Clan bearbeiten", style=discord.ButtonStyle.blurple, custom_id="clan:edit")
    async def edit(self, interaction: discord.Interaction, button: ui.Button):
        clan = await self.db.get_clan(owner_id=interaction.user.id)
        if not clan or not clan.get("accepted"):
            return await interaction.response.send_message(
                "❌ **Du bist kein Clan-Owner eines aktiven Clans.**",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🛠️ Clan bearbeiten",
            description="Hier kannst du die Einstellungen deines Clans anpassen.",
            color=discord.Color.blue()
        )

        await interaction.response.send_message(
            embed=embed,
            view=ClanEditView(self.db, clan),
            ephemeral=True
        )


class ClanCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = ClanDB()

    async def cog_load(self):
        self.bot.add_view(ClanMainView(self.db))

    @commands.command(name="clan-setup")
    @commands.has_permissions(administrator=True)
    async def clan_setup(self, ctx):
        embed = discord.Embed(
            title="⚔️ Clans",
            description="Erstelle deinen eigenen Clan oder tritt einem bestehenden Clan bei!",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=ClanMainView(self.db))
        await ctx.message.delete()

    @commands.command(name='clan-edit')
    async def clan_edit(self, ctx):
        clan = await self.db.get_clan(owner_id=ctx.author.id)

        if not clan or not clan.get("accepted"):
            return await ctx.send(
                "❌ **Du bist kein Clan-Owner eines aktiven Clans.**"
            )

        embed = discord.Embed(
            title="🛠️ Clan bearbeiten",
            description="Hier kannst du die Einstellungen deines Clans anpassen.",
            color=discord.Color.blue()
        )

        await ctx.send(
            embed=embed,
            view=ClanEditView(self.db, clan)
        )


async def setup(bot):
    await bot.add_cog(ClanCog(bot))
