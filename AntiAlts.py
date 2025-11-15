import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
team_chat_id = 1426513807357775903

class AntiAlts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return

        zeitspanne = timedelta(weeks=3)
        grenzdatum_utc = datetime.now(timezone.utc) - zeitspanne
        created = member.created_at

        neu = False
        noicon = False
        if created > grenzdatum_utc:
            neu = True

        if member.avatar is None:
            noicon = True


        if neu // noicon:
            team_chat = self.bot.get_channel(team_chat_id)

            embed = discord.Embed(
                title=f"Potentieller Alt-Account!",
                description=f"Ein Benutzer {member.mention} ist dem Server beigetreten, welcher vielleicht ein Alt-Account ist \n \n",
            )
            if neu and noicon:
                embed.add_field(name="__📄 Grund:__",
                                value="Kein Profilbild, \n"
                                "Neuer Account")
            elif neu and not noicon:
                embed.add_field(name="__📄 Grund:__",
                                value="Neuer Account")

            elif noicon and not neu:
                embed.add_field(name="__📄 Grund:__",
                                value="Kein Profilbild")

            team_chat.send(embed=embed, content="<@&1426266215558414387>")

async def setup(bot):
    await bot.add_cog(AntiAlts(bot))
