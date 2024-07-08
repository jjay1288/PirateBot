import os
import json
import aiohttp
import interactions
from interactions import listen, SlashContext, ComponentContext, StringSelectMenu, StringSelectOption
from interactions.api.events import Ready, GuildScheduledEventCreate, GuildScheduledEventDelete, GuildScheduledEventUpdate
from config import DEV_GUILD
from src import logutil
from datetime import datetime, timezone

logger = logutil.init_logger(os.path.basename(__file__))

EVENTS_FILE = 'events.json'

class RSVP(interactions.Extension):
    def __init__(self, bot):
        self.bot = bot
        self.bot_token = os.environ.get("TOKEN")
        logger.debug("Initializing RSVP extension...")

        # Load or initialize events list
        if os.path.exists(EVENTS_FILE):
            with open(EVENTS_FILE, 'r') as f:
                self.events = json.load(f)
        else:
            self.events = []

        # Load squadron roles
        with open('sq_roles.json') as f:
            self.squadron_roles = json.load(f)['squadron_roles']

        logger.debug("RSVP extension initialized.")

    @listen(Ready)
    async def on_ready(self, event: Ready):
        logger.debug("Bot is ready, fetching events...")
        await self.fetch_all_events()
        logger.debug("Events fetched and stored.")

    @listen(GuildScheduledEventCreate)
    async def on_guild_scheduled_event_create(self, event: GuildScheduledEventCreate):
        logger.debug(f"New event created: {event.scheduled_event.name}")
        await self.fetch_all_events()  # Fetch all events again
        logger.debug("Events updated and saved to file.")

    @listen(GuildScheduledEventDelete)
    async def on_guild_scheduled_event_delete(self, event: GuildScheduledEventDelete):
        logger.debug(f"Event deleted: {event.scheduled_event.name}")
        await self.fetch_all_events()  # Fetch all events again
        logger.debug("Events updated and saved to file.")

    @listen(GuildScheduledEventUpdate)
    async def on_guild_scheduled_event_update(self, event: GuildScheduledEventUpdate):
        logger.debug(f"Event updated: {event.after.name}")
        await self.fetch_all_events()  # Fetch all events again
        logger.debug("Events updated and saved to file.")

    def save_events_to_file(self):
        now = datetime.now(timezone.utc)
        unique_events = {}
        for event in self.events:
            event_time = datetime.strptime(event['scheduled_start_time'], '%Y-%m-%dT%H:%M:%S%z')
            if event_time > now:
                unique_events[event['id']] = event
        self.events = list(unique_events.values())

        with open(EVENTS_FILE, 'w') as f:
            json.dump(self.events, f, indent=4)

    async def fetch_all_events(self):
        self.events = []  # Clear current events to avoid duplicates
        for guild in self.bot.guilds:
            events = await self.fetch_events(guild.id)
            self.events.extend(events)
        self.save_events_to_file()

    async def fetch_events(self, guild_id):
        url = f"https://discord.com/api/v10/guilds/{guild_id}/scheduled-events"
        headers = {"Authorization": f"Bot {self.bot_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    events = await response.json()
                    events_sorted = sorted(events, key=lambda x: x["scheduled_start_time"])
                    return events_sorted
                else:
                    logger.error(f"Failed to fetch events: {response.status}")
                    return []

    @interactions.slash_command(
        name="getpilots",
        description="Display a menu of all events",
        scopes=[DEV_GUILD] if DEV_GUILD else None
    )
    async def getpilots_command(self, ctx: SlashContext):
        logger.debug("getpilots command invoked.")
        if not self.events:
            await ctx.send("No events found.")
            return

        # Limit to the next 24 upcoming events
        upcoming_events = self.events[:24]

        options = [StringSelectOption(label=event["name"][:25], value=str(event["id"])) for event in upcoming_events]
        select_menu = StringSelectMenu(
            *options,
            placeholder="Choose an event...",
            custom_id="select_event",
            min_values=1,
            max_values=1
        )

        await ctx.send("Select an event:", components=[select_menu])

    @interactions.component_callback("select_event")
    async def handle_select_event(self, ctx: ComponentContext):
        event_id = ctx.values[0]  # Directly access values from the context
        await ctx.message.delete()  # Delete the message with the select menu
        await self.sort_participants(ctx, event_id)

    async def sort_participants(self, ctx, event_id: str):
        guild_id = ctx.guild_id

        event_details = await self.get_event_details(guild_id, event_id)
        if not event_details:
            await ctx.send("Failed to fetch event details.")
            return

        event_title = event_details.get("name", "Unknown Event")
        event_date = event_details.get("scheduled_start_time", "Unknown Date")

        participants = await self.get_interested_people(guild_id, event_id)
        if not participants:
            await ctx.send("No interested users found or unable to fetch data.")
            return

        squadrons = self.sort_into_squadrons(participants)

        embed = interactions.Embed(
            title=f"{event_title}",
            description=f"Date: {event_date}",
            color=0x1a9ca8
        )
        embed.set_author(name="Current Attendance")
        embed.set_footer(text="Attendance sorted by squadron")

        for squadron, members in squadrons.items():
            if members:
                member_list = "\n".join(members)
                embed.add_field(name=f"{squadron} ({len(members)} currently attending):", value=member_list, inline=False)

        await ctx.send(embeds=embed)

    async def get_event_details(self, guild_id, event_id):
        url = f"https://discord.com/api/v10/guilds/{guild_id}/scheduled-events/{event_id}"
        headers = {"Authorization": f"Bot {self.bot_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to fetch event details: {response.status}")
                    return None

    async def get_interested_people(self, guild_id, event_id, limit=100):
        url = f"https://discord.com/api/v10/guilds/{guild_id}/scheduled-events/{event_id}/users"
        headers = {"Authorization": f"Bot {self.bot_token}"}
        params = {"limit": limit, "with_member": "true"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    users = await response.json()
                    participants = []
                    for user in users:
                        member = user.get('member', user['user'])
                        nickname = member.get('nick') or user['user']['username']
                        role_ids = member.get('roles', [])
                        participants.append((nickname, role_ids))
                    return participants
                else:
                    logger.error(f"Failed to fetch users: {response.status}")
                    return []

    def sort_into_squadrons(self, participants):
        squadrons = {name: [] for name in self.squadron_roles.values()}
        squadrons["Unsorted"] = []

        for nickname, role_ids in participants:
            sorted_flag = False
            for role_id in role_ids:
                squadron_name = self.squadron_roles.get(str(role_id))
                if squadron_name:
                    squadrons[squadron_name].append(nickname)
                    sorted_flag = True
                    break
            if not sorted_flag:
                squadrons["Unsorted"].append(nickname)

        return squadrons

def setup(bot):
    logger.debug("Setting up RSVP extension...")
    RSVP(bot)
    logger.debug("RSVP extension setup complete")
