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
        if clan_tag: query["tag"] = clan_tag
        if owner_id: query["owner_id"] = owner_id
        return await self.settings.find_one(query)

    async def get_user_clan(self, user_id: int):
        return await self.members.find_one({"members": user_id})

    async def create_clan(self, data):
        await self.settings.insert_one(data)

    async def update_clan(self, clan_tag, data):
        await self.settings.update_one({"tag": clan_tag}, {"$set": data})

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

    async def get_all_accepted_clans(self):
        cursor = self.settings.find({"accepted": True})
        return await cursor.to_list(length=100)

class ClanApplicationModal(ui.Modal, title="Clan erstellen"):
    name = ui.TextInput(label="Clan Name", placeholder="z.B. Die Drachenjäger", min_length=3, max_length=20)
    tag = ui.TextInput(label="Clan Tag", placeholder="z.B. DRG", min_length=2, max_length=5)
    description = ui.TextInput(label="Beschreibung", style=discord.TextStyle.paragraph, max_length=200)
    color = ui.TextInput(label="Clan Farbe (Hex)", placeholder="#ff0000", min_length=7, max_length=7)

    def __init__(self, db: ClanDB):
        super().__init__()
        self.db = db

    async def on_submit(self, interaction: discord.Interaction):
        if not re.match(HEX_COLOR_REGEX, self.color.value):
            return await interaction.response.send_message("❌ Ungültiger Hex-Code!", ephemeral=True)

        existing = await self.db.get_clan(clan_tag=self.tag.value.upper())
        if existing:
            return await interaction.response.send_message("❌ Dieser Clan-Tag ist bereits vergeben!", ephemeral=True)

        clan_data = {
            "name": self.name.value,
            "tag": self.tag.value.upper(),
            "description": self.description.value,
            "color": self.color.value,
            "owner_id": interaction.user.id,
            "accepted": False,
            "created_at": int(time.time())
        }
        await self.db.create_clan(clan_data)

        admin_channel = interaction.guild.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            embed = discord.Embed(title="Neue Clan-Anfrage", color=discord.Color.blue())
            embed.add_field(name="Name", value=self.name.value)
            embed.add_field(name="Tag", value=self.tag.value.upper())
            embed.add_field(name="Besitzer", value=interaction.user.mention)
            await admin_channel.send(embed=embed, view=ClanApprovalView(self.db, clan_data))

        await interaction.response.send_message("✅ Dein Clan wurde zur Überprüfung eingereicht!", ephemeral=True)

class ClanApprovalView(ui.View):
    def __init__(self, db: ClanDB, clan_data: dict):
        super().__init__(timeout=None)
        self.db = db
        self.clan_data = clan_data

    @ui.button(label="Annehmen", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        owner = guild.get_member(self.clan_data["owner_id"])
        
        if not owner:
            return await interaction.response.send_message("Besitzer nicht mehr auf dem Server.", ephemeral=True)

        try:
            # Rolle erstellen
            color_value = int(self.clan_data["color"].lstrip("#"), 16)
            role = await guild.create_role(name=f"Clan | {self.clan_data['tag']}", color=discord.Color(color_value))
            
            # Kategorie finden
            category = guild.get_channel(CLAN_PARENT_CATEGORY_ID)
            
            # Overwrites für den Kanal definieren
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            }

            # Kanal IN der Kategorie erstellen (Fix für deinen Fehler)
            # create_text_channel wird auf dem guild-Objekt aufgerufen, nicht create_category
            channel = await guild.create_text_channel(
                name=f"clan-{self.clan_data['tag']}", 
                category=category if isinstance(category, discord.CategoryChannel) else None, 
                overwrites=overwrites
            )

            await self.db.update_clan(self.clan_data["tag"], {
                "accepted": True,
                "role_id": role.id,
                "channel_id": channel.id
            })
            await self.db.add_member(self.clan_data["tag"], owner.id)
            await owner.add_roles(role)

            await interaction.message.delete()
            await interaction.response.send_message(f"✅ Clan {self.clan_data['tag']} wurde erstellt.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Fehlende Berechtigungen!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Fehler: {e}", ephemeral=True)

    @ui.button(label="Ablehnen", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: ui.Button):
        await self.db.settings.delete_one({"tag": self.clan_data["tag"]})
        await interaction.message.delete()
        await interaction.response.send_message("❌ Clan abgelehnt.", ephemeral=True)

class ClanJoinView(ui.View):
    def __init__(self, db: ClanDB, clans: list):
        super().__init__(timeout=60)
        self.db = db
        self.clans = clans
        self.index = 0

    def create_embed(self):
        clan = self.clans[self.index]
        embed = discord.Embed(
            title=f"Clan: {clan['name']} [{clan['tag']}]", 
            description=clan['description'], 
            color=discord.Color.from_str(clan['color'])
        )
        embed.set_footer(text=f"Clan {self.index + 1} von {len(self.clans)}")
        return embed

    @ui.button(label="⬅️", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, button: ui.Button):
        self.index = (self.index - 1) % len(self.clans)
        await interaction.response.edit_message(embed=self.create_embed())

    @ui.button(label="Beitreten", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: ui.Button):
        clan = self.clans[self.index]
        user_clan = await self.db.get_user_clan(interaction.user.id)
        
        if user_clan:
            return await interaction.response.send_message("❌ Du bist bereits in einem Clan!", ephemeral=True)

        role = interaction.guild.get_role(clan.get("role_id"))
        if role:
            try:
                await interaction.user.add_roles(role)
            except:
                pass

        await self.db.add_member(clan["tag"], interaction.user.id)
        await interaction.response.send_message(f"✅ Willkommen im Clan {clan['name']}!", ephemeral=True)

    @ui.button(label="➡️", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: ui.Button):
        self.index = (self.index + 1) % len(self.clans)
        await interaction.response.edit_message(embed=self.create_embed())

class ClanMainView(ui.View):
    def __init__(self, db: ClanDB):
        super().__init__(timeout=None)
        self.db = db

    @ui.button(label="Clan erstellen", style=discord.ButtonStyle.green, custom_id="clan_create")
    async def create(self, interaction: discord.Interaction, button: ui.Button):
        user_clan = await self.db.get_user_clan(interaction.user.id)
        if user_clan:
            return await interaction.response.send_message("❌ Du bist bereits in einem Clan!", ephemeral=True)
        await interaction.response.send_modal(ClanApplicationModal(self.db))

    @ui.button(label="Clan beitreten", style=discord.ButtonStyle.blue, custom_id="clan_join")
    async def join(self, interaction: discord.Interaction, button: ui.Button):
        clans = await self.db.get_all_accepted_clans()
        if not clans:
            return await interaction.response.send_message("❌ Es gibt aktuell keine Clans.", ephemeral=True)
        view = ClanJoinView(self.db, clans)
        await interaction.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)

    @ui.button(label="Clan verlassen", style=discord.ButtonStyle.red, custom_id="clan_leave")
    async def leave(self, interaction: discord.Interaction, button: ui.Button):
        user_clan_data = await self.db.get_user_clan(interaction.user.id)
        if not user_clan_data:
            return await interaction.response.send_message("❌ Du bist in keinem Clan.", ephemeral=True)
        
        clan_tag = user_clan_data["tag"]
        clan_info = await self.db.get_clan(clan_tag=clan_tag)
        
        if clan_info and "role_id" in clan_info:
            role = interaction.guild.get_role(clan_info["role_id"])
            if role: await interaction.user.remove_roles(role)

        await self.db.remove_member(clan_tag, interaction.user.id)
        await interaction.response.send_message("✅ Du hast den Clan verlassen.", ephemeral=True)

class ClanCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = ClanDB()

    async def cog_load(self):
        self.bot.add_view(ClanMainView(self.db))

    @commands.command(name="clan-setup")
    @commands.has_permissions(administrator=True)
    async def clan_setup(self, ctx):
        embed = discord.Embed(title="⚔️ Clans", description="Erstelle deinen eigenen Clan oder tritt einem bei!", color=discord.Color.blue())
        await ctx.send(embed=embed, view=ClanMainView(self.db))
        await ctx.message.delete()

async def setup(bot):
    await bot.add_cog(ClanCog(bot))
