import discord
from discord.ext import commands
from discord import ui
from discord.utils import get
import motor.motor_asyncio as motor
import time
import re
import asyncio
import os
import dotenv

dotenv.load_dotenv()
MONGODB_URI = os.getenv("MONGO_URI")
DB_NAME = "serverdata"
CLAN_SETTINGS_COLLECTION = "clansettings"
CLAN_MEMBERS_COLLECTION = "clanmembers"
ADMIN_CHANNEL_ID = 1446594790555648042
GUILD_ID = 1424501227521314979

EDIT_COOLDOWN_SECONDS = 2 * 24 * 60 * 60

HEX_COLOR_REGEX = r'^#[0-9A-Fa-f]{6}$'

class ClanDB:
    def __init__(self, bot):
        self.client = motor.AsyncIOMotorClient(MONGODB_URI)
        self.db = self.client[DB_NAME]
        self.settings_col = self.db[CLAN_SETTINGS_COLLECTION]
        self.members_col = self.db[CLAN_MEMBERS_COLLECTION]
        self.bot = bot

    async def get_clan(self, clan_tag=None, owner_id=None):
        query = {}
        if clan_tag:
            query["tag"] = clan_tag
        if owner_id:
            query["owner_id"] = owner_id
        return await self.settings_col.find_one(query)

    async def insert_clan_setting(self, settings):
        await self.settings_col.insert_one(settings)

    async def delete_clan_setting(self, clan_tag):
        await self.settings_col.delete_one({"tag": clan_tag})

    async def update_clan_setting(self, clan_tag, update_data):
        await self.settings_col.update_one({"tag": clan_tag}, {"$set": update_data})

    async def get_all_accepted_clans(self):
        return await self.settings_col.find({"accepted": True}).to_list(length=None)

    async def get_clan_members(self, clan_tag):
        return await self.members_col.find_one({"tag": clan_tag})

    async def add_member(self, clan_tag, user_id):
        await self.members_col.update_one(
            {"tag": clan_tag},
            {"$addToSet": {"members": user_id}},
            upsert=True
        )

    async def remove_member(self, clan_tag, user_id):
        await self.members_col.update_one(
            {"tag": clan_tag},
            {"$pull": {"members": user_id}}
        )

class ClanCreationModal(ui.Modal, title="✏️ Clan erstellen"):
    def __init__(self, db_handler: ClanDB):
        super().__init__()
        self.db_handler = db_handler

    name = ui.TextInput(label="Clanname", placeholder="z.B. Die Minecrafter")
    tag = ui.TextInput(label="Clan-Kürzel (max. 5 Zeichen)", max_length=5, placeholder="z.B. MC_R")
    color = ui.TextInput(label="Farbe (HEX Code)", max_length=7, placeholder="#RRGGBB")

    full_desc = ui.TextInput(label="Beschreibung (Ziele, Vorhaben etc.)", style=discord.TextStyle.paragraph)

    approval_required = ui.TextInput(label='Zustimmung nötig? (Ja/Nein)', max_length=3, placeholder='Ja oder Nein')

    async def on_submit(self, interaction: discord.Interaction):
        if not re.fullmatch(HEX_COLOR_REGEX, self.color.value):
            return await interaction.response.send_message("❌ **Ungültiger HEX Code.** Bitte verwende das Format #RRGGBB.", ephemeral=True)

        approval_text = self.approval_required.value.lower()
        if approval_text not in ["ja", "nein"]:
            return await interaction.response.send_message("❌ **Ungültige Eingabe für Zustimmung.** Bitte 'Ja' oder 'Nein' eingeben.", ephemeral=True)

        approval_bool = approval_text == "ja"

        existing_clan_tag = await self.db_handler.get_clan(clan_tag=self.tag.value.upper())
        existing_clan_name = await self.db_handler.settings_col.find_one({"name": self.name.value})

        if existing_clan_tag:
            return await interaction.response.send_message(f"❌ Das Clan-Kürzel **{self.tag.value.upper()}** existiert bereits.", ephemeral=True)
        if existing_clan_name:
            return await interaction.response.send_message(f"❌ Der Clanname **{self.name.value}** existiert bereits.", ephemeral=True)

        clan_data = {
            "name": self.name.value,
            "tag": self.tag.value.upper(),
            "color": self.color.value,
            "short_desc": self.full_desc.value[:20],
            "full_desc": self.full_desc.value,
            "approval_required": approval_bool,
            "owner_id": interaction.user.id,
            "created_at": time.time(),
            "accepted": False,
            "last_edit": time.time(),
        }

        await self.db_handler.insert_clan_setting(clan_data)

        admin_channel = interaction.guild.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            embed = discord.Embed(
                title=f"🚨 Neue Clan-Erstellung: {self.name.value} [{self.tag.value.upper()}]",
                color=discord.Color.red()
            )
            embed.add_field(name="Owner", value=interaction.user.mention, inline=False)
            embed.add_field(name="Kürzel", value=self.tag.value.upper())
            embed.add_field(name="Farbe", value=self.color.value)
            embed.add_field(name="Kurz-Beschreibung", value=clan_data["short_desc"], inline=False)
            embed.add_field(name="Zustimmung nötig", value="Ja" if approval_bool else "Nein")
            embed.add_field(name="Volle Beschreibung", value=self.full_desc.value, inline=False)

            view = ClanApprovalView(self.db_handler, self.tag.value.upper(), interaction.user.id)
            await admin_channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ Dein Clan **{self.name.value}** wurde zur Überprüfung eingereicht! Du wirst benachrichtigt.",
            ephemeral=True
        )

class ClanApprovalView(ui.View):
    def __init__(self, db_handler: ClanDB, clan_tag: str = None, owner_id: int = None):
        super().__init__(timeout=None)
        self.db_handler = db_handler
        self.clan_tag = clan_tag
        self.owner_id = owner_id

    async def create_clan_structure(self, guild: discord.Guild, clan_data: dict):
        owner = guild.get_member(self.owner_id)
        if not owner:
            print(f"Owner {self.owner_id} nicht auf dem Server gefunden.")
            return

        admin_role_name = f"{self.clan_tag}-Admin"
        member_role_name = f"{self.clan_tag}-Member"

        admin_role = get(guild.roles, name=admin_role_name)
        member_role = get(guild.roles, name=member_role_name)

        if not admin_role:
            admin_role = await guild.create_role(name=admin_role_name, color=discord.Color.from_str(clan_data["color"]))
        if not member_role:
            member_role = await guild.create_role(name=member_role_name)

        await owner.add_roles(admin_role, member_role)
        await self.db_handler.add_member(self.clan_tag, self.owner_id)
        category_overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, connect=False),
            admin_role: discord.PermissionOverwrite(read_messages=True, connect=True, send_messages=True),
            member_role: discord.PermissionOverwrite(read_messages=True, connect=True, send_messages=True),
        }

        category_name = f"Clan - {self.clan_tag}"
        category = await guild.create_category(category_name, overwrites=category_overwrites)
        overwrites_general = category_overwrites.copy()

        base_admin_overwrite = category_overwrites[admin_role]

        overwrites_general[admin_role] = discord.PermissionOverwrite(
            allow=base_admin_overwrite.allow,
            deny=base_admin_overwrite.deny,
            manage_messages=True,
            manage_channels=True,
        )

        general_text_channel = await category.create_text_channel(
            f"{self.clan_tag.lower()}-chat",
            overwrites=overwrites_general,
            topic=f"Der allgemeine Chat von Clan {clan_data['name']}"
        )
        overwrites_admin = category_overwrites.copy()

        overwrites_admin[admin_role] = discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            manage_messages=True,
            mention_everyone=True,
            manage_channels=True,
        )
        overwrites_admin[member_role] = discord.PermissionOverwrite(read_messages=False, send_messages=False)


        announcement_channel = await category.create_text_channel(
            f"{self.clan_tag.lower()}-admin-news",
            overwrites=overwrites_admin,
            topic=f"Wichtige Nachrichten und Ankündigungen für Clan {clan_data['name']} (Admin/Owner)"
        )

        overwrites_stage = category_overwrites.copy()
        base_member_overwrite = category_overwrites[member_role]
        base_admin_overwrite = category_overwrites[admin_role]

        # Aktualisiere Admin-Rechte
        overwrites_stage[admin_role] = discord.PermissionOverwrite(
            allow=base_admin_overwrite.allow,
            deny=base_admin_overwrite.deny,
            connect=True,
            speak=True,
            request_to_speak=False,
            manage_channels=True,
            move_members=True,
            manage_roles=True
        )

        # Aktualisiere Member-Rechte
        overwrites_stage[member_role] = discord.PermissionOverwrite(
            allow=base_member_overwrite.allow,
            deny=base_member_overwrite.deny,
            connect=True,
            speak=False,
            request_to_speak=True
        )

        await category.create_stage_channel(
            f"{self.clan_tag.lower()}-stage",
            overwrites=overwrites_stage
        )

        voice_channel_1 = await category.create_voice_channel(f"{self.clan_tag} Voicechat 1", overwrites=category_overwrites)
        voice_channel_2 = await category.create_voice_channel(f"{self.clan_tag} Voicechat 2", overwrites=category_overwrites)


        await self.db_handler.update_clan_setting(self.clan_tag, {
            "accepted": True,
            "category_id": category.id,
            "admin_role_id": admin_role.id,
            "member_role_id": member_role.id,
            "general_text_id": general_text_channel.id,
            "admin_text_id": announcement_channel.id,
            "voice_channels": [voice_channel_1.id, voice_channel_2.id]
        })

    @ui.button(label="✅ Akzeptieren", style=discord.ButtonStyle.green, custom_id="clan_approval_accept")
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()

        if not self.clan_tag:
            try:
                title = interaction.message.embeds[0].title
                match = re.search(r'\[([A-Za-z0-9_]{1,5})\]$', title)
                if match:
                    self.clan_tag = match.group(1)
            except:
                return await interaction.edit_original_response(content="❌ Clan-Kürzel konnte nicht aus dem Embed gelesen werden.", view=None)

        clan_data = await self.db_handler.get_clan(clan_tag=self.clan_tag)
        if not clan_data:
            return await interaction.edit_original_response(content="❌ Clan nicht gefunden.", view=None)

        self.owner_id = clan_data["owner_id"]

        if clan_data["accepted"]:
            return await interaction.edit_original_response(content="⚠️ Dieser Clan wurde bereits akzeptiert.", view=None)

        try:
            await self.create_clan_structure(interaction.guild, clan_data)

            owner = interaction.guild.get_member(self.owner_id)
            if owner:
                await owner.send(f"🎉 Dein Clan **{clan_data['name']} [{self.clan_tag}]** wurde vom Team akzeptiert! Deine Clan-Struktur wurde erstellt.")

            new_embed = interaction.message.embeds[0].copy()
            new_embed.title = f"✅ Akzeptiert: {clan_data['name']} [{self.clan_tag}]"
            new_embed.color = discord.Color.green()
            new_embed.add_field(name="Akzeptiert von", value=interaction.user.mention, inline=False)

            await interaction.edit_original_response(embed=new_embed, view=None)

        except Exception as e:
            await interaction.followup.send(f"❌ Fehler bei der Erstellung der Clan-Struktur: `{e}`", ephemeral=True)
            await self.db_handler.delete_clan_setting(self.clan_tag)

    @ui.button(label="❌ Ablehnen", style=discord.ButtonStyle.red, custom_id="clan_approval_reject")
    async def reject(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()

        if not self.clan_tag:
            try:
                title = interaction.message.embeds[0].title
                match = re.search(r'\[([A-Za-z0-9_]{1,5})\]$', title)
                if match:
                    self.clan_tag = match.group(1)
            except:
                return await interaction.edit_original_response(content="❌ Clan-Kürzel konnte nicht aus dem Embed gelesen werden.", view=None)

        clan_data = await self.db_handler.get_clan(clan_tag=self.clan_tag)
        if not clan_data:
            return await interaction.edit_original_response(content="❌ Clan nicht gefunden.", view=None)

        self.owner_id = clan_data["owner_id"]

        await self.db_handler.delete_clan_setting(self.clan_tag)

        owner = interaction.guild.get_member(self.owner_id)
        if owner:
            await owner.send(f"🚫 Dein Clan **{clan_data['name']} [{self.clan_tag}]** wurde vom Team abgelehnt. Der Eintrag wurde aus der Datenbank entfernt.")

        new_embed = interaction.message.embeds[0].copy()
        new_embed.title = f"❌ Abgelehnt: {clan_data['name']} [{self.clan_tag}]"
        new_embed.color = discord.Color.red()
        new_embed.add_field(name="Abgelehnt von", value=interaction.user.mention, inline=False)

        await interaction.edit_original_response(embed=new_embed, view=None)

class ClanJoinView(ui.View):
    def __init__(self, db_handler: ClanDB, clans: list, current_index: int = 0):
        super().__init__(timeout=600)
        self.db_handler = db_handler
        self.clans = clans
        self.current_index = current_index
        self.update_buttons()

    def create_clan_embed(self, clan_data: dict) -> discord.Embed:
        hex_color = int(clan_data["color"].replace("#", ""), 16)
        embed = discord.Embed(
            title=f"**[{clan_data['tag']}]** {clan_data['name']} (Clan {self.current_index + 1} von {len(self.clans)})",
            description=f"*{clan_data.get('short_desc', 'Keine Kurzbeschreibung verfügbar')}*",
            color=discord.Color(hex_color)
        )
        embed.add_field(name="Zustimmung nötig", value="Ja" if clan_data["approval_required"] else "Nein")
        embed.add_field(name="Volle Beschreibung", value=clan_data["full_desc"], inline=False)
        return embed

    def update_buttons(self):
        self.children = []

        back_button = ui.Button(emoji="◀️", style=discord.ButtonStyle.secondary, custom_id="join_view_back")
        back_button.callback = self.go_back
        back_button.disabled = self.current_index == 0
        self.add_item(back_button)

        join_button = ui.Button(label="🤝 Beitreten", style=discord.ButtonStyle.green, custom_id="join_view_join")
        join_button.callback = self.join_clan
        self.add_item(join_button)

        next_button = ui.Button(emoji="▶️", style=discord.ButtonStyle.secondary, custom_id="join_view_next")
        next_button.callback = self.go_next
        next_button.disabled = self.current_index == len(self.clans) - 1
        self.add_item(next_button)

    async def go_back(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.current_index -= 1
        self.update_buttons()
        await interaction.edit_original_response(embed=self.create_clan_embed(self.clans[self.current_index]), view=self)

    async def go_next(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.current_index += 1
        self.update_buttons()
        await interaction.edit_original_response(embed=self.create_clan_embed(self.clans[self.current_index]), view=self)

    async def join_clan(self, interaction: discord.Interaction):
        clan_data = self.clans[self.current_index]
        clan_tag = clan_data["tag"]
        member_doc = await self.db_handler.get_clan_members(clan_tag)
        if member_doc and interaction.user.id in member_doc.get("members", []):
            return await interaction.response.send_message(f"⚠️ Du bist bereits Mitglied im Clan **{clan_tag}**.", ephemeral=True)

        if clan_data["approval_required"]:
            owner = interaction.guild.get_member(clan_data["owner_id"])
            await interaction.response.send_message(
                f"✅ Deine Beitrittsanfrage für **{clan_data['name']}** wurde an den Owner ({owner.mention if owner else '???'}) gesendet.",
                ephemeral=True
            )
        else:
            await self.db_handler.add_member(clan_tag, interaction.user.id)

            guild = interaction.guild
            member_role = guild.get_role(clan_data["member_role_id"])
            if member_role:
                await interaction.user.add_roles(member_role)

            await interaction.response.send_message(
                f"🎉 Du bist dem Clan **{clan_data['name']} [{clan_tag}]** beigetreten!",
                ephemeral=True
            )

class ClanMainView(ui.View):
    def __init__(self, db_handler: ClanDB):
        super().__init__(timeout=None)
        self.db_handler = db_handler

    @ui.button(label="✏️ Clan erstellen", style=discord.ButtonStyle.primary, custom_id="main_create_clan")
    async def create_clan(self, interaction: discord.Interaction, button: ui.Button):
        existing_clan = await self.db_handler.get_clan(owner_id=interaction.user.id)
        if existing_clan:
            return await interaction.response.send_message(f"❌ Du bist bereits Owner des Clans **{existing_clan['name']} [{existing_clan['tag']}]**.", ephemeral=True)

        await interaction.response.send_modal(ClanCreationModal(self.db_handler))

    @ui.button(label="🤝 Clan beitreten", style=discord.ButtonStyle.secondary, custom_id="main_join_clan")
    async def join_clan_list(self, interaction: discord.Interaction, button: ui.Button):
        accepted_clans = await self.db_handler.get_all_accepted_clans()

        if not accepted_clans:
            return await interaction.response.send_message("❌ Es existieren momentan keine Clans, denen du beitreten könntest.", ephemeral=True)

        view = ClanJoinView(self.db_handler, accepted_clans)
        await interaction.response.send_message(
            embed=view.create_clan_embed(accepted_clans[0]),
            view=view,
            ephemeral=True
        )

class ClanEditMainView(ui.View):
    def __init__(self, db_handler: ClanDB, clan_data: dict):
        super().__init__(timeout=600)
        self.db_handler = db_handler
        self.clan_data = clan_data

        fields_to_edit = {
            "name": "Clanname",
            "color": "Farbe",
            "full_desc": "Volle Beschreibung",
            "approval_required": "Zustimmung nötig (Ja/Nein)",
        }

        for i, (key, label) in enumerate(fields_to_edit.items()):
            button = ui.Button(label=f"Ändere {label}", style=discord.ButtonStyle.secondary, custom_id=f"edit_menu_{key}")
            button.callback = lambda interaction, k=key, l=label: self.open_edit_modal(interaction, k, l)
            self.add_item(button)

    async def open_edit_modal(self, interaction: discord.Interaction, key: str, label: str):
        latest_clan_data = await self.db_handler.get_clan(clan_tag=self.clan_data['tag'])
        if not latest_clan_data:
            return await interaction.response.send_message("❌ Dein Clan wurde nicht in der Datenbank gefunden.", ephemeral=True)

        modal = ClanEditModal(self.db_handler, latest_clan_data, key, label)
        await interaction.response.send_modal(modal)

class ClanEditModal(ui.Modal, title="Clan-Wert bearbeiten"):
    def __init__(self, db_handler: ClanDB, clan_data: dict, key: str, label: str):
        super().__init__()
        self.db_handler = db_handler
        self.clan_data = clan_data
        self.key = key
        self.label = label

        current_value = str(clan_data.get(key, ''))

        style = discord.TextStyle.paragraph if key in ["full_desc", "short_desc"] else discord.TextStyle.short

        if key == "short_desc":
            style = discord.TextStyle.short

        self.new_value = ui.TextInput(label=f"Neuer Wert für {label}", default=current_value, style=style)
        self.add_item(self.new_value)

    async def on_submit(self, interaction: discord.Interaction):
        new_value = self.new_value.value.strip()

        if self.key == "color" and not re.fullmatch(HEX_COLOR_REGEX, new_value):
            return await interaction.response.send_message("❌ **Ungültiger HEX Code.** Bitte verwende das Format #RRGGBB.", ephemeral=True)

        if self.key == "approval_required":
            lower_value = new_value.lower()
            if lower_value not in ["ja", "nein"]:
                return await interaction.response.send_message("❌ **Ungültige Eingabe.** Bitte 'Ja' oder 'Nein' eingeben.", ephemeral=True)
            new_value_for_db = lower_value == "ja"
        else:
            new_value_for_db = new_value

        update_data = {
            self.key: new_value_for_db,
            "last_edit": time.time()
        }

        if self.key == "full_desc":
            update_data["short_desc"] = new_value_for_db[:20]

        await self.db_handler.update_clan_setting(self.clan_data["tag"], update_data)

        await interaction.response.send_message(
            f"✅ Wert für **{self.label}** von Clan **{self.clan_data['tag']}** erfolgreich auf `{new_value}` aktualisiert.",
            ephemeral=True
        )

class Clansystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_handler = ClanDB(bot)
        self.bot.add_view(ClanMainView(self.db_handler))
        self.bot.add_view(ClanApprovalView(self.db_handler))

    @commands.group(name="clan", invoke_without_command=True)
    async def clan_group(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @clan_group.command(name="clan-setup")
    @commands.has_permissions(administrator=True)
    async def clan_setup(self, ctx):
        embed = discord.Embed(
            title="⚔️ Clan erstellen oder beitreten",
            description="Wähle eine Aktion, um einen Clan zu erstellen oder beizutreten!",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=ClanMainView(self.db_handler))
        await ctx.message.delete()

    @clan_group.command(name="clan-edit")
    async def clan_edit(self, ctx):
        clan_data = await self.db_handler.get_clan(owner_id=ctx.author.id)

        if not clan_data:
            return await ctx.send("❌ Du bist kein Owner eines akzeptierten Clans.")

        last_edit_time = clan_data.get("last_edit", 0)
        cooldown_end = last_edit_time + EDIT_COOLDOWN_SECONDS

        if time.time() < cooldown_end:
            time_left = int(cooldown_end - time.time())
            hours, remainder = divmod(time_left, 3600)
            minutes, seconds = divmod(remainder, 60)
            return await ctx.send(f"❌ Du kannst deinen Clan nur alle 2 Tage bearbeiten. Verbleibende Zeit: **{hours}h {minutes}m {seconds}s**.", ephemeral=True)

        embed = discord.Embed(
            title=f"🛠️ Clan-Bearbeitung: {clan_data['name']} [{clan_data['tag']}]",
            description="Wähle, welchen Wert du bearbeiten möchtest.",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed, view=ClanEditMainView(self.db_handler, clan_data), ephemeral=True)
        await ctx.message.delete()


async def setup(bot):
    await bot.add_cog(Clansystem(bot))