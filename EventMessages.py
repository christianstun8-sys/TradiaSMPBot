from discord.ext import commands
import discord

class BoostMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.boost_channel_id = 1446594963877138535

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        if before.premium_subscription_count < after.premium_subscription_count:
            boost_channel = self.bot.get_channel(self.boost_channel_id)
            booster_member = None
            for member in after.members:
                if member.premium_since is not None and member.premium_since.date() == discord.utils.utcnow().date():
                    booster_member = member
                    break

            if booster_member and self.boost_channel_id:
                embed = discord.Embed(
                    title="✨ Server Boost! ✨",
                    description=f"Vielen Dank an {booster_member.mention} für den boost! Wir danken dir für deinen Support!",
                    color=discord.Color.magenta()
                )
                await boost_channel.send(embed=embed, content=f"{booster_member.mention}")

class WelcomeMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.welcome_channel_id = 1446594963877138535

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        target_channel = self.bot.get_channel(self.welcome_channel_id)
        if target_channel is None:
            print(f"Fehler: Der Kanal mit der ID {self.welcome_channel_id} wurde nicht gefunden oder der Bot hat keine Berechtigung, ihn zu sehen.")
            return

        welcome_embed = discord.Embed(
            title="Willkommen!👋",
            description=f"Willkommen auf dem TradiaSMP Discord Server. {member.mention}. Bitte folge unseren Regeln und joine dem Minecraft Server. Viel Spaß!",
            color=discord.Color.blue()
        )
        welcome_embed.set_thumbnail(url=member.avatar.url)
        await target_channel.send(embed=welcome_embed)


async def setup(bot):
    await bot.add_cog(BoostMessage(bot))
    await bot.add_cog(WelcomeMessage(bot))