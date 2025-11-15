from discord.ext import commands
import discord

class ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="ping", description="Bekomme die Latence des Bots.")
    async def ping(self, interaction: discord.Interaction):
        latency_ms = round(self.bot.latency * 1000)
        ping_embed = discord.Embed(
            title="Pong! 🏓",
            description=f"Ich brauchte {latency_ms}ms um zu antworten!",
            color=discord.Color.orange()
        )

        await interaction.response.send_message(embed=ping_embed)

async def setup(bot):
    await bot.add_cog(ping(bot))