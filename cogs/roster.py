import discord
from discord.ext import commands
import xlsxwriter
import json

class Roster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('sq_roles.json') as f:
            self.squadron_roles = json.load(f)['squadron_roles']

    @commands.command(name='roster')
    async def roster_command(self, ctx):
        await ctx.message.delete()
        await self.create_roster(ctx)

    async def create_roster(self, ctx):
        guild = ctx.guild
        workbook = xlsxwriter.Workbook('roster.xlsx')
        sheet1 = workbook.add_worksheet('Sheet 1')
        sheet2 = workbook.add_worksheet('Sheet 2')
        sheet3 = workbook.add_worksheet('Sheet 3')

        # Headers for the sheets
        headers = ['Nickname', 'Username', 'Roles', 'Joined At']
        for col, header in enumerate(headers):
            sheet1.write(0, col, header)
            sheet2.write(0, col, header)
            sheet3.write(0, col, header)

        row1, row2, row3 = 1, 1, 1

        for member in guild.members:
            roles = [role.name for role in member.roles if role.name != "@everyone"]
            role_ids = [role.id for role in member.roles if role.name != "@everyone"]
            data = [
                member.name,
                member.nick,
                ', '.join(roles),
                member.joined_at.strftime('%Y-%m-%d %H:%M:%S') if member.joined_at else 'N/A',
            ]

            sorted_flag = False
            for role_id in role_ids:
                squadron_name = self.squadron_roles.get(str(role_id))
                if squadron_name:
                    if squadron_name not in ["Reserve"]:
                        for col, value in enumerate(data):
                            sheet1.write(row1, col, value)
                        row1 += 1
                    else:
                        for col, value in enumerate(data):
                            sheet2.write(row2, col, value)
                        row2 += 1
                    sorted_flag = True
                    break
            if not sorted_flag:
                for col, value in enumerate(data):
                    sheet3.write(row3, col, value)
                row3 += 1

        workbook.close()
        await ctx.send("Roster has been created and saved as 'roster.xlsx'.")

async def setup(bot):
    await bot.add_cog(Roster(bot))
    print("Roster cog setup complete")
