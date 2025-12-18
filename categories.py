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
                print(f"Kategorien {roles_to_add} an {after.display_name} vergeben.")
            except discord.Forbidden:
                print("Fehler: Bot hat keine Berechtigung, Rollen zu vergeben.")

async def setup(bot):
    await bot.add_cog(RoleCategoryCog(bot))