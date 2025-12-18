import discord
from discord.ext import commands
from discord import ui
from discord.utils import get
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
        if clan_tag: query["tag"] = clan_tag
        if owner_id: query["owner_id"] = owner_id
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
        await self.members_col.update_one({"tag": clan_tag}, {"$addToSet": {"members": user_id}}, upsert=True)

class ClanCreationModal(ui.Modal, title="✏️ Clan erstellen"):
    def __init__(self, db_handler: ClanDB):
        super().__init__()
        self.db_handler = db_handler

    name = ui.TextInput(label="Clanname", placeholder="z.B. Die Minecrafter")
    tag = ui.TextInput(label="Clan-Kürzel (max. 5 Zeichen)", max_length=5, placeholder="z.B. MC_R")
    color = ui.TextInput(label="Farbe (HEX Code)", max_length=7, placeholder="#RRGGBB")
    full_desc = ui.TextInput(label="Beschreibung", style=discord.TextStyle.paragraph)
    approval_required = ui.TextInput(label='Zustimmung nötig? (Ja/Nein)', max_length=3, placeholder='Ja')

    async def on_submit(self, interaction: discord.Interaction):
        if not re.fullmatch(HEX_COLOR_REGEX, self.color.value):
            return await interaction.response.send_message("❌ Ungültiger HEX Code.", ephemeral=True)

        tag_upper = self.tag.value.upper()
        if await self.db_handler.get_clan(clan_tag=tag_upper):
            return await interaction.response.send_message(f"❌ Kürzel {tag_upper} existiert bereits.", ephemeral=True)

        clan_data = {
            "name": self.name.value,
            "tag": tag_upper,
            "color": self.color.value,
            "short_desc": self.full_desc.value[:20],
            "full_desc": self.full_desc.value,
            "approval_required": self.approval_required.value.lower() == "ja",
            "owner_id": interaction.user.id,
            "created_at": time.time(),
            "accepted": False,
            "last_edit": time.time(),
        }
        await self.db_handler.insert_clan_setting(clan_data)

        admin_channel = interaction.guild.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            embed = discord.Embed(title=f"🚨 Neue Clan-Anfrage: {clan_data['name']} [{tag_upper}]", color=discord.Color.orange())
            embed.add_field(name="Owner", value=interaction.user.mention)
            embed.add_field(name="Beschreibung", value=clan_data["full_desc"], inline=False)
            await admin_channel.send(embed=embed, view=ClanApprovalView(self.db_handler, tag_upper, interaction.user.id))

        await interaction.response.send_message("✅ Antrag eingereicht!", ephemeral=True)

class ClanApprovalView(ui.View):
    def __init__(self, db_handler: ClanDB, clan_tag: str = None, owner_id: int = None):
        super().__init__(timeout=None)
        self.db_handler = db_handler
        self.clan_tag = clan_tag
        self.owner_id = owner_id

    async def create_structure(self, guild, clan_data):
        admin_role = await guild.create_role(name=f"{clan_data['tag']}-Admin", color=discord.Color.from_str(clan_data["color"]))
        member_role = await guild.create_role(name=f"{clan_data['tag']}-Member")

        owner = guild.get_member(clan_data["owner_id"])
        if owner: await owner.add_roles(admin_role, member_role)

        category = await guild.create_category(f"Clan - {clan_data['tag']}")
        await category.set_permissions(guild.default_role, read_messages=False)
        await category.set_permissions(admin_role, read_messages=True, manage_messages=True, manage_channels=True)
        await category.set_permissions(member_role, read_messages=True)

        chat = await category.create_text_channel(f"{clan_data['tag'].lower()}-chat")
        voice = await category.create_voice_channel(f"{clan_data['tag']} Voice")

        await self.db_handler.update_clan_setting(clan_data["tag"], {
            "accepted": True,
            "admin_role_id": admin_role.id,
            "member_role_id": member_role.id,
            "category_id": category.id
        })
        await self.db_handler.add_member(clan_data["tag"], clan_data["owner_id"])

    @ui.button(label="✅ Akzeptieren", style=discord.ButtonStyle.green, custom_id="persistent:approve")
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        tag = re.search(r'\[(\w+)\]', interaction.message.embeds[0].title).group(1)
        clan_data = await self.db_handler.get_clan(clan_tag=tag)
        if clan_data and not clan_data["accepted"]:
            await self.create_structure(interaction.guild, clan_data)
            await interaction.edit_original_response(content=f"✅ Clan {tag} genehmigt.", embed=None, view=None)

    @ui.button(label="❌ Ablehnen", style=discord.ButtonStyle.red, custom_id="persistent:reject")
    async def reject(self, interaction: discord.Interaction, button: ui.Button):
        tag = re.search(r'\[(\w+)\]', interaction.message.embeds[0].title).group(1)
        await self.db_handler.delete_clan_setting(tag)
        await interaction.response.edit_message(content=f"❌ Clan {tag} abgelehnt.", embed=None, view=None)

class ClanJoinView(ui.View):
    def __init__(self, db_handler: ClanDB, clans: list, current_index: int = 0):
        super().__init__(timeout=300)
        self.db_handler = db_handler
        self.clans = clans
        self.current_index = current_index

    def create_embed(self):
        clan = self.clans[self.current_index]
        embed = discord.Embed(title=f"{clan['name']} [{clan['tag']}]", description=clan['full_desc'], color=discord.Color.from_str(clan['color']))
        embed.set_footer(text=f"Clan {self.current_index + 1} von {len(self.clans)}")
        return embed

    @ui.button(emoji="◀️", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, button: ui.Button):
        self.current_index = (self.current_index - 1) % len(self.clans)
        await interaction.response.edit_message(embed=self.create_embed())

    @ui.button(label="Beitreten", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: ui.Button):
        clan = self.clans[self.current_index]
        if clan["approval_required"]:
            await interaction.response.send_message("📩 Anfrage an den Leader gesendet.", ephemeral=True)
        else:
            role = interaction.guild.get_role(clan["member_role_id"])
            if role: await interaction.user.add_roles(role)
            await self.db_handler.add_member(clan["tag"], interaction.user.id)
            await interaction.response.send_message(f"🎉 Willkommen im Clan {clan['name']}!", ephemeral=True)

    @ui.button(emoji="▶️", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: ui.Button):
        self.current_index = (self.current_index + 1) % len(self.clans)
        await interaction.response.edit_message(embed=self.create_embed())

class ClanMainView(ui.View):
    def __init__(self, db_handler: ClanDB):
        super().__init__(timeout=None)
        self.db_handler = db_handler

    @ui.button(label="✏️ Clan erstellen", style=discord.ButtonStyle.primary, custom_id="persistent:create")
    async def create(self, interaction: discord.Interaction, button: ui.Button):
        if await self.db_handler.get_clan(owner_id=interaction.user.id):
            return await interaction.response.send_message("❌ Du besitzt bereits einen Clan.", ephemeral=True)
        await interaction.response.send_modal(ClanCreationModal(self.db_handler))

    @ui.button(label="🤝 Clan beitreten", style=discord.ButtonStyle.secondary, custom_id="persistent:join")
    async def join(self, interaction: discord.Interaction, button: ui.Button):
        clans = await self.db_handler.get_all_accepted_clans()
        if not clans:
            return await interaction.response.send_message("❌ Keine aktiven Clans gefunden.", ephemeral=True)
        view = ClanJoinView(self.db_handler, clans)
        await interaction.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)

class Clansystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_handler = ClanDB(bot)

    async def cog_load(self):
        self.bot.add_view(ClanMainView(self.db_handler))
        self.bot.add_view(ClanApprovalView(self.db_handler))

    @commands.group(name="clan", invoke_without_command=True)
    async def clan_group(self, ctx):
        await ctx.send_help(ctx.command)

    @clan_group.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def clan_setup(self, ctx):
        embed = discord.Embed(
            title="⚔️ Clan-System",
            description="Gründe deinen eigenen Clan oder schließe dich einer bestehenden Gemeinschaft an!",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=ClanMainView(self.db_handler))
        await ctx.message.delete()

async def setup(bot):
    await bot.add_cog(Clansystem(bot))