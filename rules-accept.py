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

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green, custom_id="persistent_accept_button")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user

        role_id = 1447150040039817450
        role = interaction.guild.get_role(role_id)

        if role in member.roles:
            await interaction.response.send_message("🤔 Du kannst die Regeln nicht akzeptieren, weil du das bereits getan hast.", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message("✅ Du hast die Regeln akzeptiert! Danke.", ephemeral=True)


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