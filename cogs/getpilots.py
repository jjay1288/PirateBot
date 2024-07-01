import json
import discord
from discord.ext import commands
import aiohttp

class GetPilots(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('sq_roles.json') as f:
            self.squadron_roles = json.load(f)['squadron_roles']

    @commands.command(name='getpilots')
    async def getpilots_command(self, ctx, event_id: str = None):
        await ctx.message.delete()
        if event_id is None:
            await self.show_event_menu(ctx)
        else:
            await interaction.message.delete()  # Delete the dropdown menu
            await self.sort_participants(ctx, event_id)

    async def show_event_menu(self, ctx):
        guild_id = ctx.guild.id
        bot_token = self.bot.http.token

        # Fetch events
        events = await self.fetch_events(guild_id, bot_token)
        if not events:
            await ctx.send("Failed to fetch events.")
            return

        # Create a menu of events
        options = [
            discord.SelectOption(label=event["name"], description=event["scheduled_start_time"], value=event["id"])
            for event in events
        ]

        select = discord.ui.Select(placeholder="Choose an event...", options=options)

        async def select_callback(interaction):
            event_id = select.values[0]
            await interaction.response.defer()  # Acknowledge the interaction
            await self.sort_participants(ctx, event_id)
            await interaction.message.delete()

        select.callback = select_callback

        view = discord.ui.View()
        view.add_item(select)

        await ctx.send("Select an event:", view=view)

    async def fetch_events(self, guild_id, bot_token):
        url = f"https://discord.com/api/v9/guilds/{guild_id}/scheduled-events"
        headers = {"Authorization": f"Bot {bot_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    events = await response.json()
                    events_sorted = sorted(events, key=lambda x: x["scheduled_start_time"])
                    return events_sorted
                else:
                    print(f"Failed to fetch events: {response.status}")
                    return None

    async def get_interested_people(self, guild_id, event_id, bot_token, limit=100):
        url = f"https://discord.com/api/v9/guilds/{guild_id}/scheduled-events/{event_id}/users"
        headers = {"Authorization": f"Bot {bot_token}"}
        params = {"limit": limit, "with_member": "true"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    users = await response.json()
                    participants = []
                    for user in users:
                        # Get the member object if it exists, else use user object
                        member = user.get('member', user['user'])
                        nickname = member.get('nick') or user['user']['username']  # Use nickname if available, else username
                        role_ids = member.get('roles', [])  # List of role IDs
                        participants.append((nickname, role_ids))
                    return participants
                else:
                    print(f"Failed to fetch users: {response.status}")
                    return []

    async def sort_participants(self, ctx, event_id: str):
        guild_id = ctx.guild.id
        bot_token = self.bot.http.token

        # Fetch event details
        print(f"Fetching event details for guild_id: {guild_id}, event_id: {event_id}")  # Debugging
        event_details = await self.get_event_details(guild_id, event_id, bot_token)
        if not event_details:
            await ctx.send("Failed to fetch event details.")
            return

        # Format event title and date
        event_title = event_details.get("name", "Unknown Event")
        event_date = event_details.get("scheduled_start_time", "Unknown Date")

        participants = await self.get_interested_people(guild_id, event_id, bot_token)
        if not participants:
            await ctx.send("No interested users found or unable to fetch data.")
            return

        squadrons = self.sort_into_squadrons(participants)

        # Create a Discord Embed with event title and date
        embed = discord.Embed(title=f"{event_title}", description=f"Date: {event_date}", color=0x1a9ca8)
        embed.set_author(name="Current Attendance")
        embed.set_footer(text="Attendance sorted by squadron")

        for squadron, members in squadrons.items():
            if members:  # Add only non-empty squadrons to the embed
                member_list = "\n".join(members)
                embed.add_field(name=f"{squadron} ({len(members)} currently attending):", value=member_list, inline=False)

        await ctx.send(embed=embed)

    async def get_event_details(self, guild_id, event_id, bot_token):
        url = f"https://discord.com/api/v9/guilds/{guild_id}/scheduled-events/{event_id}"
        headers = {"Authorization": f"Bot {bot_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    event_data = await response.json()
                    return event_data
                else:
                    print(f"Failed to fetch event details: {response.status}")
                    return None

    def sort_into_squadrons(self, participants):
        squadrons = {name: [] for name in self.squadron_roles.values()}
        squadrons["Unsorted"] = []

        for nickname, role_ids in participants:
            sorted_flag = False
            for role_id in role_ids:
                squadron_name = self.squadron_roles.get(role_id)
                if squadron_name:
                    squadrons[squadron_name].append(nickname)
                    sorted_flag = True
                    break
            if not sorted_flag:
                squadrons["Unsorted"].append(nickname)

        return squadrons

async def setup(bot):
    await bot.add_cog(GetPilots(bot))
    print("GetPilots cog setup complete")  # Debugging
