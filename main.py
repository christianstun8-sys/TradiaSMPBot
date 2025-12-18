import os
import dotenv
import discord
from discord import app_commands
from discord.ext import commands

class TradiaBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='t!', help_command=None, intents=discord.Intents.all())



    async def on_ready(self):
        print(f'Eingeloggt als {self.user.name} (ID: {self.user.id})')
        print('--------------------')
        print('Bot ist bereit!')
        await self.change_presence(status=discord.Status.online, activity=discord.Game(name="📫 DM für Support"))

    @app_commands.command(name='sync', description='ADMIN: Commandsync')
    @app_commands.checks.has_permissions(administrator=True)
    async def sync(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            synced = await self.tree.sync()
            await interaction.followup.send(f"✅ {len(synced)} Slash-Commands gesynct", ephemeral=True)
        except Exception as e:
            print(e)
            await interaction.response.send_message(f"❌ Fehler! {e}", ephemeral=True)



    async def setup_hook(self):
        print("--------------------")
        print("Starte Cogs....")
        cogs = [
            'AntiAlts',
            'Ticket',
            'SyncCommand',
            'rules-de',
            'rules-eng',
            'rules-accept',
            'TempVoice',
            'EventMessages',
            'Ping',
            'SupportForum',
            'modmail',
            'faq-system',
            'clans',
            'categories'
        ]

        for cog in cogs:

            try:
                await bot.load_extension(cog)
                print(f"✅ Cog '{cog}' erfolgreich geladen.")
            except Exception as e:
                print(f"❌ Fehler beim Laden des Cogs '{cog}': {e}")

dotenv.load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
bot = TradiaBot()
bot.run(TOKEN)
