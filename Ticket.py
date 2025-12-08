import discord
import discord.app_commands
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio

# Bewerbung: Admin
# Allgemein: ab Supporter
# Nutzermeldung: ab Mods
# Sonstiges: ab Supporter

# Admin > Mod > Supporter


# --- Konfigurationsvariablen ---
OPEN_CATEGORY_ID = 1447666165584494774
CLAIMED_CATEGORY_ID = 1447666351899676844
CLOSED_CATEGORY_ID = 1447666069736128542

supporter_role_id = 1446594629804884008
mod_role_id = 1446594622993203365
administrator_role_id = 1446594618673201232

# Definiere die Rollen-Konstanten neu basierend auf der Zugriffslogik und den vorhandenen IDs
# Alle Tickets sollen für diese Rolle zugänglich sein
ALL_TICKETS_ACCESS_ROLE_ID = 1426266215558414387

# Diese Konstanten wurden angepasst:
# Bewerbung: Nur Admin
APPLICATION_ROLE_ID = administrator_role_id
# Allgemeine Hilfe / Sonstiges: Ab Supporter (Supporter, Mod, Admin)
GENERAL_SUPPORT_ROLE_ID = supporter_role_id
# Nutzer-Meldung: Ab Mod (Mod, Admin)
MOD_TEAM_ROLE_ID = mod_role_id

TICKETS_DB = 'tickets.db'
# ------------------------------

async def init_db():
    async with aiosqlite.connect(TICKETS_DB) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                                                   channel_id INTEGER PRIMARY KEY,
                                                   user_id INTEGER NOT NULL,
                                                   status TEXT NOT NULL,
                                                   claimed_by INTEGER
            )
            """
        )
        await db.commit()

async def get_ticket_data(channel_id):
    async with aiosqlite.connect(TICKETS_DB) as db:
        async with db.execute("SELECT user_id, status, claimed_by FROM tickets WHERE channel_id = ?", (channel_id,)) as cursor:
            return await cursor.fetchone()

async def move_ticket_category(channel: discord.TextChannel, status: str, claimed_by_id: int = None):
    category_id = None
    if status == 'closed':
        category_id = CLOSED_CATEGORY_ID
    elif status == 'open':
        category_id = OPEN_CATEGORY_ID
    elif status == 'claimed':
        category_id = CLAIMED_CATEGORY_ID

    if category_id:
        category = channel.guild.get_channel(category_id)
        if category and isinstance(category, discord.CategoryChannel):
            await channel.edit(category=category)


class ConfirmDeleteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Ja, löschen!", style=discord.ButtonStyle.red, custom_id="confirm_delete_button")
    async def confirm_delete_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Ticket wird in 5 Sekunden gelöscht....", ephemeral=True)

        channel = interaction.channel
        await asyncio.sleep(5)

        async with aiosqlite.connect(TICKETS_DB) as db:
            await db.execute("DELETE FROM tickets WHERE channel_id = ?", (channel.id,))
            await db.commit()

        await channel.delete()

    @discord.ui.button(label="❌ Abbrechen", style=discord.ButtonStyle.green, custom_id="cancel_delete_button")
    async def cancel_delete_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="✅ Abgebrochen!",
                              color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=None)

class ClosedTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔓 Öffnen", style=discord.ButtonStyle.green, custom_id="ticket_open_button")
    async def open_ticket_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("⚠️ Du hast dazu keine Berechtigung!", ephemeral=True)

        channel = interaction.channel

        # Rollen, die immer Zugriff haben sollen (für die Bereinigungslogik beim Öffnen/Schließen)
        all_team_role_ids = [supporter_role_id, mod_role_id, administrator_role_id, ALL_TICKETS_ACCESS_ROLE_ID]

        overwrites_to_update = {}
        for target, permissions in channel.overwrites.items():
            if isinstance(target, (discord.Member, discord.User, discord.Role)) and permissions.read_messages:
                is_team_or_bot = isinstance(target, discord.Role) and target.id in all_team_role_ids or target.id == interaction.guild.me.id

                ticket_data_temp = await get_ticket_data(channel.id)
                is_ticket_creator = ticket_data_temp and target.id == ticket_data_temp[0]

                if not is_team_or_bot and not is_ticket_creator:
                    overwrites_to_update[target] = discord.PermissionOverwrite(
                        send_messages=True,
                        read_messages=True,
                        read_message_history=True
                    )


        ticket_data = await get_ticket_data(channel.id)
        if not ticket_data:
            return await interaction.response.send_message("❌ Fehler: Ticket nicht in der Datenbank gefunden!", ephemeral=True)

        user_id = ticket_data[0]
        member = interaction.guild.get_member(user_id)
        if member:
            overwrites_to_update[member] = discord.PermissionOverwrite(
                send_messages=True,
                read_messages=True,
                read_message_history=True
            )

        for target, overwrite in overwrites_to_update.items():
            await channel.set_permissions(target, overwrite=overwrite)

        async with aiosqlite.connect(TICKETS_DB) as db:
            await db.execute("UPDATE tickets SET status = ? WHERE channel_id = ?", ('open', channel.id))
            await db.commit()

        await move_ticket_category(channel, 'open')

        embed = discord.Embed(title="🔓 Ticket geöffnet", description=f"{interaction.user.mention} hat das Ticket geöffnet.", color=discord.Color.dark_blue())
        await interaction.response.send_message(embed=embed, view=OpenTicketView())

    @discord.ui.button(label="⛔ Löschen", style=discord.ButtonStyle.red, custom_id="delete_ticket_button")
    async def delete_ticket_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("⚠️ Du hast keine Berechtigung dazu!", ephemeral=True)

        embed = discord.Embed(
            title="🛑 Bist du sicher?",
            description="Das kann nicht rückgängig gemacht werden. Das Ticket wird **für immer** gelöscht sein.",
            color=discord.Color.dark_red()
        )
        await interaction.response.send_message(embed=embed, view=ConfirmDeleteView(), ephemeral=True)

class OpenTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Schließen", style=discord.ButtonStyle.red, custom_id="ticket_close_button")
    async def close_ticket_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("⚠️ Du hast keine Berechtigung dazu!", ephemeral=True)

        channel = interaction.channel

        # Rollen, die immer Zugriff haben sollen (für die Bereinigungslogik beim Öffnen/Schließen)
        all_team_role_ids = [supporter_role_id, mod_role_id, administrator_role_id, ALL_TICKETS_ACCESS_ROLE_ID]

        overwrites_to_update = {}
        # Gehe alle Overwrites durch, um alle User/Rollen zu finden, die keine Team-Rolle sind, aber schreiben dürfen
        for target, permissions in channel.overwrites.items():
            is_team_or_bot = (isinstance(target, discord.Role) and target.id in all_team_role_ids) or target.id == interaction.guild.me.id

            if not is_team_or_bot and permissions.send_messages:
                overwrites_to_update[target] = discord.PermissionOverwrite(
                    send_messages=False,
                    read_messages=True,
                    read_message_history=True
                )

        # Stelle sicher, dass der Ticketersteller auch das Schreiben verliert
        ticket_data = await get_ticket_data(channel.id)
        if ticket_data:
            user_id = ticket_data[0]
            member = interaction.guild.get_member(user_id)
            if member:
                overwrites_to_update[member] = discord.PermissionOverwrite(
                    send_messages=False,
                    read_messages=True,
                    read_message_history=True
                )

        for target, overwrite in overwrites_to_update.items():
            await channel.set_permissions(target, overwrite=overwrite)

        async with aiosqlite.connect(TICKETS_DB) as db:
            await db.execute("UPDATE tickets SET status = ?, claimed_by = NULL WHERE channel_id = ?", ('closed', channel.id))
            await db.commit()

        await move_ticket_category(channel, 'closed')

        embed = discord.Embed(
            title="🔒 Ticket geschlossen",
            description=f"{interaction.user.mention} hat das Ticket geschlossen.",
            color=discord.Color.dark_blue()
        )
        await interaction.response.send_message(embed=embed, view=ClosedTicketView())

class TicketClaimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="👍 Claimen/Freigeben", style=discord.ButtonStyle.secondary, custom_id="ticket_claim_button")
    async def claim_ticket_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message("⚠️ Du hast keine Berechtigung dazu!", ephemeral=True)

        ticket_data = await get_ticket_data(interaction.channel.id)
        if not ticket_data:
            return await interaction.response.send_message("❌ Fehler: Ticket nicht in der Datenbank gefunden!", ephemeral=True)

        claimed_by_id = ticket_data[2]
        new_claimed_by_id = None

        async with aiosqlite.connect(TICKETS_DB) as db:
            if claimed_by_id is None:
                new_claimed_by_id = interaction.user.id
                await db.execute("UPDATE tickets SET claimed_by = ?, status = 'claimed' WHERE channel_id = ?", (new_claimed_by_id, interaction.channel.id))
                embed = discord.Embed(description=f"{interaction.user.mention} hat dieses Ticket **geclaimt**.", color=discord.Color.dark_blue())
                await move_ticket_category(interaction.channel, 'claimed', claimed_by_id=new_claimed_by_id)
            elif claimed_by_id == interaction.user.id:
                await db.execute("UPDATE tickets SET claimed_by = NULL, status = 'open' WHERE channel_id = ?", (interaction.channel.id,))
                embed = discord.Embed(description=f"{interaction.user.mention} hat das Ticket **freigegeben**.", color=discord.Color.dark_blue())
                await move_ticket_category(interaction.channel, 'open', claimed_by_id=None)
            else:
                claimer = interaction.guild.get_member(claimed_by_id)
                claimer_mention = claimer.mention if claimer else f"einem Benutzer (<@{claimed_by_id}>)"
                return await interaction.response.send_message(f"Dieses Ticket ist bereits von {claimer_mention} geclaimt.", ephemeral=True)

            await db.commit()
            await interaction.response.send_message(embed=embed)


class PersistentTicketTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            # discord.SelectOption(label="MC Server Entbannungsantrag", value="mc_unban_appeal", description="Ticket für eine Entbannungsanfrage auf dem Minecraft Server.", emoji="🔨"), # ENTFERNT
            discord.SelectOption(label="Nutzer-Meldung", value="user_report", description="Melde einen Nutzer, der gegen die Regeln verstößt.", emoji="🚫"),
            discord.SelectOption(label="Allgemeine Hilfe", value="general_help", description="Stelle allgemeine Fragen zum Discord oder Server.", emoji="❓"),
            discord.SelectOption(label="Bewerbung", value="application", description="Reiche deine Teambewerbung ein.", emoji="📝"),
            discord.SelectOption(label="Sonstiges", value="other", description="Für alle anderen Anfragen.", emoji="✉️")
        ]
        super().__init__(placeholder="Wähle den Ticket-Typ...", min_values=1, max_values=1, options=options, custom_id="persistent_ticket_type_select")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        selected_value = self.values[0]
        guild = interaction.guild
        member = interaction.user

        ping_role_ids = []
        ticket_title = ""
        ticket_description = ""

        # Lege die Rollen fest, die Zugriff haben sollen
        team_access_roles = []

        # --- Neue Logik basierend auf der Notiz ---
        # Standard-Rollen-Hierarchie: Supporter_ID (niedrig) < Mod_ID < Admin_ID (hoch)

        if selected_value == "user_report":
            # Nutzermeldung: ab Mods (Mod, Admin)
            ping_role_ids.append(MOD_TEAM_ROLE_ID) # MOD_TEAM_ROLE_ID ist mod_role_id
            team_access_roles = [mod_role_id, administrator_role_id]
            ticket_title = f"Nutzer-Meldung von {member.display_name}"
            ticket_description = "Bitte gib den Namen des Nutzers und Beweise (Screenshots/Videos) des Verstoßes an."

        elif selected_value == "general_help":
            # Allgemein: ab Supporter (Supporter, Mod, Admin)
            ping_role_ids.append(GENERAL_SUPPORT_ROLE_ID) # GENERAL_SUPPORT_ROLE_ID ist supporter_role_id
            team_access_roles = [supporter_role_id, mod_role_id, administrator_role_id]
            ticket_title = f"Allgemeine Hilfe für {member.display_name}"
            ticket_description = "Bitte beschreibe, wobei du Hilfe brauchst, so detailliert wie möglich. Das Team wird dir in Kürze helfen."

        elif selected_value == "application":
            # Bewerbung: Admin (Nur Admin)
            ping_role_ids.append(APPLICATION_ROLE_ID) # APPLICATION_ROLE_ID ist administrator_role_id
            team_access_roles = [administrator_role_id]
            ticket_title = f"Bewerbung von {member.display_name}"
            ticket_description = "Bitte stelle dich kurz vor und beschreibe, wofür du dich bewirbst und warum du dafür geeignet bist."

        elif selected_value == "other":
            # Sonstiges: ab Supporter (Supporter, Mod, Admin)
            ping_role_ids.append(GENERAL_SUPPORT_ROLE_ID) # GENERAL_SUPPORT_ROLE_ID ist supporter_role_id
            team_access_roles = [supporter_role_id, mod_role_id, administrator_role_id]
            ticket_title = f"Sonstige Anfrage von {member.display_name}"
            ticket_description = "Bitte beschreibe dein Anliegen so detailliert wie möglich."

        # Rollen, die als Mention im Ticket landen sollen (optional, oft nur die 'Startrolle')
        roles_to_ping = [guild.get_role(r_id) for r_id in ping_role_ids if guild.get_role(r_id)]
        ping_roles_mentions = " ".join([role.mention for role in roles_to_ping])

        # Entferne Duplikate in team_access_roles (falls welche entstehen) und sorge dafür, dass die IDs gültig sind
        final_access_role_ids = list(set(team_access_roles))

        async with aiosqlite.connect(TICKETS_DB) as db:
            async with db.execute("SELECT channel_id FROM tickets WHERE user_id = ? AND status IN ('open', 'claimed')", (member.id,)) as cursor:
                existing_ticket = await cursor.fetchone()

            if existing_ticket:
                return await interaction.followup.send(f"Du hast bereits ein offenes Ticket: <#{existing_ticket[0]}>", ephemeral=True)

            category = guild.get_channel(OPEN_CATEGORY_ID)
            if not category:
                await interaction.followup.send("❌ Fehler: Kategorie nicht gefunden!", ephemeral=True)
                return

            op = member
            all_access_role = guild.get_role(ALL_TICKETS_ACCESS_ROLE_ID)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                op: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                # Die ALL_TICKETS_ACCESS_ROLE_ID hat immer Zugriff
                all_access_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }

            # Füge die spezifischen Rollen mit Zugriff hinzu
            for role_id in final_access_role_ids:
                if role_id != ALL_TICKETS_ACCESS_ROLE_ID:
                    role = guild.get_role(role_id)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            channel_name_prefix = selected_value.split('_')[0] if selected_value.find('_') != -1 else selected_value
            channel_name = f"ticket-{channel_name_prefix}-{member.name}"[:100]
            new_channel = await guild.create_text_channel(name=channel_name.lower(), overwrites=overwrites, category=category)

            await db.execute(
                "INSERT INTO tickets (channel_id, user_id, status) VALUES (?, ?, ?)",
                (new_channel.id, member.id, 'open')
            )
            await db.commit()

        embed = discord.Embed(
            title=ticket_title,
            description=ticket_description,
            color=discord.Color.dark_blue()
        )

        await new_channel.send(embed=embed, view=OpenTicketView(), content=f"{member.mention} {ping_roles_mentions}")
        await new_channel.send(view=TicketClaimView())

        await interaction.followup.send(f"Dein Ticket wurde erstellt: {new_channel.mention}", ephemeral=True)

        current_view = self.view

        current_view.clear_items()

        current_view.add_item(PersistentTicketTypeSelect())

        try:
            await interaction.message.edit(view=current_view)
        except discord.HTTPException:
            pass


class TicketCreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PersistentTicketTypeSelect())


class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        await init_db()
        self.bot.add_view(TicketCreateView())
        self.bot.add_view(OpenTicketView())
        self.bot.add_view(ClosedTicketView())
        self.bot.add_view(ConfirmDeleteView())
        self.bot.add_view(TicketClaimView())

    @commands.command(name="ticket-panel")
    @commands.has_permissions(manage_messages=True)
    async def ticketpanel(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Ticket erstellen",
            description="Wähle unten den Grund für dein neues Ticket aus.",
            color=discord.Color.dark_blue()
        )
        await ctx.send(embed=embed, view=TicketCreateView())

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("⚠️ Du hast nicht die Berechtigung, dies zu tun!", ephemeral=True)
        else:
            print(error)


class AddMember(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="ticket-mitglied-hinzufügen", description="Fügt ein Mitglied zum Ticket hinzu.")
    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.describe(member="Der hinzuzufügende Benutzer.")
    async def ticket_add_member(self, interaction: discord.Interaction, member: discord.Member):
        channel = interaction.channel

        if not channel.name.startswith("ticket-"):
            return await interaction.response.send_message("⚠️ Dieser Befehl kann nur in einem Ticket-Channel ausgeführt werden!", ephemeral=True)

        overwrites = channel.overwrites_for(member)
        overwrites.read_messages = True
        overwrites.send_messages = True

        try:
            await channel.set_permissions(member, overwrite=overwrites)
            await interaction.response.send_message(f"{member.mention} wurde dem Ticket hinzugefügt.")

        except discord.Forbidden:
            await interaction.response.send_message("⚠️ Ich habe nicht die Berechtigung, dies zu tun. Bitte überprüfe meine Rollen.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Fehler: {e}", ephemeral=True)


    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(" ⚠️ Du hast nicht die Berechtigung, dies zu tun!", ephemeral=True)
        else:
            print(error)


class RemoveMember(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="ticket-mitglied-entfernen", description="Entfernt ein Mitglied aus dem Ticket.")
    @discord.app_commands.checks.has_permissions(manage_messages=True)
    @discord.app_commands.describe(member="Der zu entfernende Benutzer.")
    async def ticket_remove_member(self, interaction: discord.Interaction, member: discord.Member):
        channel = interaction.channel

        if not channel.name.startswith("ticket-"):
            return await interaction.response.send_message("⚠️ Dieser Befehl kann nur in einem Ticket-Channel ausgeführt werden!", ephemeral=True)

        overwrites = channel.overwrites_for(member)
        overwrites.read_messages = False
        overwrites.send_messages = False

        try:
            await channel.set_permissions(member, overwrite=overwrites)
            await interaction.response.send_message(f"{member.mention} wurde aus dem Ticket entfernt.")
        except discord.Forbidden:
            await interaction.response.send_message("⚠️ Ich habe nicht die Berechtigung, dies zu tun. Bitte überprüfe meine Rollen.", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(" ⚠️ Du hast nicht die Berechtigung, dies zu tun!", ephemeral=True)

        else:
            print(error)


class AdminCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="ticket-admin-only", description="Ein Befehl, der nur von Admins ausgeführt werden kann.")
    @discord.app_commands.checks.has_role(administrator_role_id)
    async def ticket_admin_only_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Erfolg: Dieser Befehl kann nur von Admins ausgeführt werden!", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingRole):
            # Sendet eine Nachricht, wenn der Benutzer die Administrator-Rolle fehlt
            await interaction.response.send_message("🛑 Zugriff verweigert! Du musst Administrator sein, um diesen Befehl zu verwenden.", ephemeral=True)
        else:
            print(error)


async def setup(bot):
    await bot.add_cog(TicketCog(bot))
    await bot.add_cog(AddMember(bot))
    await bot.add_cog(RemoveMember(bot))
    await bot.add_cog(AdminCommands(bot))