import discord
from discord.ext import commands


class RulesEng(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    english_rules_embed = discord.Embed(
        description="# 🇬🇧 Rules (English)",
        color=discord.Color.dark_blue()
    )

    english_rules_embed.add_field(
        name="\n 📜 Welcome to the TradiaSMP Community! | SERVER RULES",
        value="We expect everyone to adhere to the **Discord Terms of Service** and the **Minecraft Server Rules** at all times."
    )

    english_rules_embed.add_field(
        name="\n ⭐ Text Channels",
        value=(
            "**1. Be Respectful.** No insults, racial, sexist, or otherwise discriminatory remarks.\n"
            "**2. No Spam & No Advertising.** Repeated messages, excessive use of Caps Lock, or unapproved self/external advertising (server invites, links, etc.) are prohibited.\n"
            "**3. Use the Correct Channels.** Stick to the topic of the respective channel (e.g., <#1426518118989168650> for questions, <#1425937090696450079> for images).\n"
            "**4. NSFW is Prohibited.** Adult content is not allowed on this server."
        ),
        inline=False
    )

    english_rules_embed.add_field(
        name="\n 🎙️ Voice Channels",
        value=(
            "**1. Quality and Consideration.** Avoid loud, disruptive, or excessive background noise. Use **Push-to-Talk** if necessary.\n"
            "**2. No Channel Hopping Spam.** Rapid, repeated switching between voice channels is prohibited.\n"
            "**3. Recordings.** Recording conversations is only allowed with the **explicit consent** of all present participants."
        ),
        inline=False
    )

    english_rules_embed.add_field(
        name="\n 🛡️ Others",
        value=(
            "**1. Avatar & Nickname.** Your profile picture and nickname must not be offensive, insulting, or misleading (e.g., impersonating staff).\n"
            "**2. Staff Instructions.** Always follow the instructions of staff members (Moderators/Admins). Their decisions are final.\n"
            "**3. Report Violations.** If you witness a rule-break, use the reporting tools or contact staff via ticket/DM. Do not engage in \"mini-moderation.\""
        ),
        inline=False
    )


    @commands.command(name="engrulesmsg", description="ADMIN: Sends the rules.")
    async def rulesmsg(self, ctx):
        if ctx.author.id == 1235134572157603841 or ctx.author.id == 1098208027913494589:
            await ctx.send(embed=self.english_rules_embed)

        else:
            pass

async def setup(bot):
    await bot.add_cog(RulesEng(bot))