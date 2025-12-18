import discord
from discord.ext import commands

class RoleCategoryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Mapping der Kategorie-IDs
        self.CATEGORY_IDS = [
            1446594614113861784, # -- Team --
            1446594644061192192, # -- Team Ping --
            1446594648192712745, # -- Leitungen --
            1446983237355438271, # -- Ingame Ränge --
            1447149377779929108, # -- STATUS --
            1447720390200918201, # -- INFOS --
            1446594661413163181, # -- Extras --
            1446594670397227128, # -- Ping Roles --
            1447152020560810100  # -- Clan Roles --
        ]

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles == after.roles:
            return

        new_roles = [r for r in after.roles if r not in before.roles]

        roles_to_add = []

        for role in new_roles:
            if role.id in self.CATEGORY_IDS:
                continue

            all_categories = sorted(
                [after.guild.get_role(cid) for cid in self.CATEGORY_IDS if after.guild.get_role(cid)],
                key=lambda x: x.position,
                reverse=True
            )

            parent_category = None
            for cat in all_categories:
                if cat.position > role.position:
                    parent_category = cat
                else:
                    break

            if parent_category and parent_category not in after.roles:
                if parent_category not in roles_to_add:
                    roles_to_add.append(parent_category)

        if roles_to_add:
            try:
                await after.add_roles(*roles_to_add, reason="Automatische Kategorie-Zuweisung")
            except discord.Forbidden:
                pass
    @commands.command(name="syncroles")
    @commands.has_permissions(administrator=True)
    async def sync_roles(self, ctx):
        """Überprüft alle User und fügt fehlende Kategorie-Rollen hinzu."""
        await ctx.send("Starte Rollen-Synchronisation... Das kann einen Moment dauern.")

        async with ctx.typing():
            # Kategorien einmalig laden und sortieren
            all_categories = sorted(
                [ctx.guild.get_role(cid) for cid in self.CATEGORY_IDS if ctx.guild.get_role(cid)],
                key=lambda x: x.position,
                reverse=True
            )

            changes_made = 0

            for member in ctx.guild.members:
                if member.bot:
                    continue

                roles_to_add = []
                for role in member.roles:
                    if role.id in self.CATEGORY_IDS or role.is_default():
                        continue

                    # Finde die passende Kategorie für diese Rolle
                    for cat in all_categories:
                        if cat.position > role.position:
                            if cat not in member.roles and cat not in roles_to_add:
                                roles_to_add.append(cat)
                            break # Höchste mögliche Kategorie gefunden

                if roles_to_add:
                    try:
                        await member.add_roles(*roles_to_add)
                        changes_made += 1
                    except discord.Forbidden:
                        continue

        await ctx.send(f"✅ Synchronisation abgeschlossen! Bei {changes_made} Mitgliedern wurden Kategorien ergänzt.")

async def setup(bot):
    await bot.add_cog(RoleCategoryCog(bot))