import discord
from discord import app_commands
from discord.ext import commands

class SyncCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="sync", description="ADMIN: Befehle syncen")
    @app_commands.checks.has_permissions(administrator=True)
    async def sync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            synced = await self.bot.tree.sync()

            successembed = discord.Embed(
                title="✅ Synchronisiert!",
                description=f"**{len(synced)}** Slash-Befehle wurden erfolgreich synchronisiert.",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=successembed, ephemeral=True)

        except Exception as e:
            print(f"Fehler beim Sync: {e}")
            failembed = discord.Embed(
                title="❌ Synchronisieren fehlgeschlagen!",
                description=f"Ein Fehler ist aufgetreten: `{e}`",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=failembed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(SyncCommand(bot))