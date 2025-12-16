import discord
from discord.ext import commands

class RoleCategoryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.category_ids = [
            1446594614113861784,
            1446594644061192192,
            1446594648192712745,
            1446983237355438271,
            1447149377779929108,
            1447720390200918201,
            1446594661413163181,
            1447152020560810100
        ]

    def get_category_ranges(self, guild):
        all_roles = sorted(guild.roles, key=lambda r: r.position)
        categories = []
        for cat_id in self.category_ids:
            role = guild.get_role(cat_id)
            if role:
                categories.append(role)

        ranges = {}
        for i in range(len(categories)):
            current_cat = categories[i]
            lower_bound = current_cat.position

            if i + 1 < len(categories):
                upper_bound = categories[i+1].position
            else:
                upper_bound = float('inf')

            ranges[current_cat.id] = (lower_bound, upper_bound)
        return ranges

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles == after.roles:
            return

        guild = after.guild
        ranges = self.get_category_ranges(guild)
        current_roles = after.roles
        roles_to_modify = list(after.roles)
        changed = False

        for cat_id, (low, high) in ranges.items():
            cat_role = guild.get_role(cat_id)
            if not cat_role:
                continue

            sub_roles_in_user = [
                r for r in current_roles
                if low < r.position < high and r.id not in self.category_ids
            ]

            has_cat = cat_role in current_roles

            if sub_roles_in_user and not has_cat:
                roles_to_modify.append(cat_role)
                changed = True
            elif not sub_roles_in_user and has_cat:
                roles_to_modify.remove(cat_role)
                changed = True

        if changed:
            await after.edit(roles=roles_to_modify)

async def setup(bot):
    await bot.add_cog(RoleCategoryCog(bot))
