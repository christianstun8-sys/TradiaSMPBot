import discord
from discord.ext import commands

class RoleCategoryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.category_ids = [
            1446594614113861784, 1446594644061192192,
            1446594648192712745, 1446983237355438271,
            1447149377779929108, 1447720390200918201,
            1446594661413163181, 1447152020560810100
        ]
        self.excluded_from_triggering = [
            123456789012345678,
        ]

    def get_category_ranges(self, guild):
        categories = [r for cat_id in self.category_ids if (r := guild.get_role(cat_id))]
        categories.sort(key=lambda r: r.position)

        ranges = {}
        for i in range(len(categories)):
            current_cat = categories[i]
            lower_bound = current_cat.position
            upper_bound = categories[i+1].position if i + 1 < len(categories) else 999
            ranges[current_cat.id] = (lower_bound, upper_bound)
        return ranges

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles == after.roles:
            return

        guild = after.guild
        if not guild.me.guild_permissions.manage_roles:
            return

        ranges = self.get_category_ranges(guild)
        current_roles = set(after.roles)
        new_roles = set(after.roles)
        changed = False

        for cat_id, (low, high) in ranges.items():
            cat_role = guild.get_role(cat_id)
            if not cat_role or cat_role >= guild.me.top_role:
                continue

            sub_roles_in_range = [
                r for r in after.roles
                if low < r.position < high
                   and r.id not in self.category_ids
                   and r.id not in self.excluded_from_triggering
                   and not r.is_default()
            ]

            is_cat_present = cat_role in current_roles
            if sub_roles_in_range and not is_cat_present:
                new_roles.add(cat_role)
                changed = True
            elif not sub_roles_in_range and is_cat_present:
                new_roles.remove(cat_role)
                changed = True

        if changed:
            try:
                await after.edit(roles=list(new_roles), reason="Rollen-Struktur Update")
            except discord.HTTPException as e:
                print(f"Fehler beim Rollen-Update: {e}")

async def setup(bot):
    await bot.add_cog(RoleCategoryCog(bot))