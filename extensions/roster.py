import os
import interactions
import xlsxwriter
import json
from config import DEV_GUILD
from src import logutil

logger = logutil.init_logger(os.path.basename(__file__))

class Roster(interactions.Extension):
    def __init__(self, bot):
        self.bot = bot
        logger.debug("Initializing Roster extension...")
        with open('sq_roles.json') as f:
            self.squadron_roles = json.load(f)['squadron_roles']
        logger.debug("Roster extension initialized.")

    @interactions.slash_command(
        name="roster",
        description="Generate a roster",
        scopes=[DEV_GUILD] if DEV_GUILD else None
    )
    async def roster_command(self, ctx: interactions.SlashContext):
        logger.debug("Roster command invoked.")
        await self.create_roster(ctx)

    def sanitize_sheet_name(self, name):
        # Replace invalid characters with underscores
        return ''.join(['_' if c in '[]:*?/\\' else c for c in name])

    async def create_roster(self, ctx: interactions.SlashContext):
        logger.debug("Creating roster...")
        guild = ctx.guild
        members = guild.members

        workbook = xlsxwriter.Workbook('roster.xlsx')
        
        # Sanitize sheet names and create sheets
        sheets = {role: workbook.add_worksheet(self.sanitize_sheet_name(role)) for role in self.squadron_roles.values()}
        sheets['Unassigned'] = workbook.add_worksheet('Unassigned')

        # Headers for the sheets
        headers = ['Nickname', 'Username', 'Roles', 'Joined At']
        for sheet in sheets.values():
            for col, header in enumerate(headers):
                sheet.write(0, col, header)

        rows = {role: 1 for role in self.squadron_roles.values()}
        rows['Unassigned'] = 1

        for member in members:
            roles = [role.name for role in member.roles if role.name != "@everyone"]
            role_ids = [role.id for role in member.roles if role.name != "@everyone"]
            data = [
                member.nick if member.nick else member.user.username,
                member.user.username,
                ', '.join(roles),
                member.joined_at.strftime('%Y-%m-%d %H:%M:%S') if member.joined_at else 'N/A',
            ]

            sorted_flag = False
            for role_id in role_ids:
                squadron_name = self.squadron_roles.get(str(role_id))
                if squadron_name:
                    sheet = sheets[squadron_name]
                    row = rows[squadron_name]
                    for col, value in enumerate(data):
                        sheet.write(row, col, value)
                    rows[squadron_name] += 1
                    sorted_flag = True
                    break
            if not sorted_flag:
                sheet = sheets['Unassigned']
                row = rows['Unassigned']
                for col, value in enumerate(data):
                    sheet.write(row, col, value)
                rows['Unassigned'] += 1

        workbook.close()
        await ctx.send(files=[interactions.File('roster.xlsx')])
        os.remove('roster.xlsx')
        logger.debug("Roster created and file sent.")

def setup(bot):
    logger.debug("Setting up Roster extension...")
    Roster(bot)
    logger.debug("Roster extension setup complete")
