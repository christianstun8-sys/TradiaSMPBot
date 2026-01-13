import discord
from discord.ext import commands

embed = discord.Embed(
    title="Regeln akzeptieren | Accept rules",
    description="Wenn du die Regeln gelesen hast, akzeptiere sie bitte. \n \n"
                "If you have read the rules, please accept them.",
    color=discord.Color.green()
)

class AcceptButtonView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green, custom_id="rules_accept_button")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user

        acceptembed = discord.Embed(
            title="✅ Regeln akzeptiert",
            description="Vielen Dank, dass du die Regeln akzeptiert hast. \n "
                    "Als nächstes solltest du <@1428119115754901665> anschreiben, wo du deinen Minecraft Account mit deinem Discord Account verknüpfen kannst.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=acceptembed, content=member.mention, ephemeral=True)

class SendMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(AcceptButtonView(bot))

    @commands.command(name="rulesacceptmsg")
    async def rulesacceptmsg(self, ctx):
        if ctx.author.id == 1235134572157603841 or ctx.author.id == 1098208027913494589:
            await ctx.send(embed=embed, view=AcceptButtonView(bot=self.bot))

async def setup(bot):
    await bot.add_cog(SendMessage(bot))
