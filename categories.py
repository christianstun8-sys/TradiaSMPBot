import discord
from discord.ext import commands

class RoleCategoryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CATEGORY_IDS = [
            1446594614113861784, 1446594644061192192, 1446594648192712745,
            1446983237355438271, 1447149377779929108, 1447720390200918201,
            1446594661413163181, 1446594670397227128, 1447152020560810100
        ]

    def get_sorted_categories(self, guild):
        """Gibt Kategorien aufsteigend nach Position sortiert zurück."""
        cats = [guild.get_role(cid) for cid in self.CATEGORY_IDS if guild.get_role(cid)]
        return sorted(cats, key=lambda x: x.position)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles == after.roles:
            return

        new_roles = [r for r in after.roles if r not in before.roles]
        all_categories = self.get_sorted_categories(after.guild)

        roles_to_add = set()

        for role in new_roles:
            if role.id in self.CATEGORY_IDS:
                continue

            for cat in all_categories:
                if cat.position > role.position:
                    if cat not in after.roles:
                        roles_to_add.add(cat)
                    break

        if roles_to_add:
            try:
                await after.add_roles(*roles_to_add, reason="Automatische Kategorie-Zuweisung")
            except discord.Forbidden:
                pass

    @commands.command(name="syncroles")
    @commands.has_permissions(administrator=True)
    async def sync_roles(self, ctx):
        await ctx.send("Starte Rollen-Synchronisation...")

        all_categories = self.get_sorted_categories(ctx.guild)
        changes_made = 0

        errors = 0

        async with ctx.typing():
            for member in ctx.guild.members:
                if member.bot: continue

                needed_for_member = set()
                for role in member.roles:
                    if role.id in self.CATEGORY_IDS or role.is_default():
                        continue

                    for cat in all_categories:
                        if cat.position > role.position:
                            if cat not in member.roles:
                                needed_for_member.add(cat)
                            break

                if needed_for_member:
                    try:
                        await member.add_roles(*needed_for_member)
                        changes_made += 1
                    except discord.Forbidden as e:
                        errors = errors + 1
                        print(f"Berechtigunsfehler bei der Kategoriezuweisung: {e}")
                        continue
                    except Exception as e:
                        errors = errors + 1
                        print(f"Fehler bei der Kategoriezuweisung: {e}")


        if errors != 0:
            await ctx.send(f"❌ Fertig! {changes_made} Mitglieder aktualisiert, dabei gab es {errors} Fehler. Bitte in der Konsole nachschauen.")
        else:
            await ctx.send(f"✅ Fertig! {changes_made} Mitglieder aktualisiert.")
        errors = 0

async def setup(bot):
    await bot.add_cog(RoleCategoryCog(bot))