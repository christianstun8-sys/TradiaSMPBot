import discord
from discord.ext import commands


class RulesDe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    german_rules_embed = discord.Embed(
        description="# 🇩🇪 Regeln (German)",
        color = discord.Color.dark_blue()
        )

    german_rules_embed.add_field(
        name="\n 📜 Willkommen in der TradiaSMP Community! | SERVER REGELN",
        value="Wir erwarten, dass jeder die **Discord Nutzungsbedingungen** und die **Minecraft Server Regeln** einhält.",
    )

    german_rules_embed.add_field(
        name="\n ⭐ Textkanäle",
        value=(
            "**1. Sei respektvoll.** - Keine Beleidigungen, rassistischen, sexistischen oder anderweitig diskriminierenden Äußerungen.\n"
            "**2. Kein Spam & keine Werbung.** - Wiederholte Nachrichten, exzessive Nutzung von Caps Lock oder Fremdwerbung (Server-Invites, Links, etc.) sind untersagt.\n"
            "**3. Nutze die richtigen Kanäle.** - Halte dich an das Thema des jeweiligen Channels (z.B. <#1426518118989168650> für Fragen, <#1425937090696450079> für Bilder).\n"
            "**4. NSFW ist verboten.** - Inhalte für Erwachsene sind auf diesem Server nicht gestattet."
        ),
        inline=False
    )

    german_rules_embed.add_field(
        name="\n 🎙 Sprachkanäle",
        value=(
            "**1. Qualität und Rücksicht.** Vermeide laute, störende Geräusche oder übermäßige Hintergrundgeräusche. Nutze **Push-to-Talk**, falls nötig.\n"
            "**2. Keine Channel-Hopping-Spams.** Das schnelle, wiederholte Wechseln zwischen Voice Channels ist untersagt.\n"
            "**3. Mitschnitte.** Aufnahmen von Gesprächen sind nur mit der **ausdrücklichen Zustimmung** aller Anwesenden erlaubt."
        ),
        inline=False
    )

    german_rules_embed.add_field(
        name="\n 🛡️ Sonstige",
        value=(
            "**1. Avatar & Nickname.** Dein Profilbild und dein Nickname dürfen nicht anstößig, beleidigend oder irreführend sein (z.B. Teammitglieder imitieren).\n"
            "**2. Anweisungen des Teams.** Befolge immer die Anweisungen der Teammitglieder (Moderatoren/Admins). Ihre Entscheidungen sind endgültig.\n"
            "**3. Melde Regelverstöße.** Wenn du einen Verstoß siehst, nutze die Meldefunktion oder kontaktiere das Team per Ticket/PN. Treibe keine \"Mini-Moderation\"."
        ),
        inline=False
    )

    @commands.command(name="gerulesmsg", description="ADMIN: Sends the rules.")
    async def rulesmsg(self, ctx):
        if ctx.author.id == 1235134572157603841 or ctx.author.id == 1098208027913494589:
            await ctx.send(embed=self.german_rules_embed)

        else:
            pass

async def setup(bot):
    await bot.add_cog(RulesDe(bot))