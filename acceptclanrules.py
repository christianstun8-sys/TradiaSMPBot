import discord
from discord.ext import commands

clanrulesaccepted_id = 1447152218716508281


embed = discord.Embed(
    title="📚 Clan-Regeln akzeptieren",
    description="Bestätige hier, dass du die Regeln für die Clans akzeptierst, um einem Clan beizutreten oder einen Clan zu erstellen.",
    color=discord.Color.green()
)

class AcceptButtonView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="✅ Akzeptieren", style=discord.ButtonStyle.green, custom_id="persistent_accept_button")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user

        role_id = clanrulesaccepted_id
        role = interaction.guild.get_role(role_id)

        if role in member.roles:
            await interaction.response.send_message("🤔 Du kannst die Clan-Regeln nicht akzeptieren, weil du das bereits getan hast.", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message("✅ Du hast die Clan-Regeln akzeptiert! Erstelle oder Tritt nun einem Clan in https://discord.com/channels/1424501227521314979/1446595019828887782 bei!", ephemeral=True)


class SendAcceptPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(AcceptButtonView(bot))

    @commands.command(name="clanrulesacceptmsg")
    @commands.has_permissions(administrator=True)
    async def rulesacceptmsg(self, ctx):
        await ctx.send(embed=embed, view=AcceptButtonView(bot=self.bot))

async def setup(bot):
    await bot.add_cog(SendAcceptPanel(bot))