import discord
from discord.ext import commands, tasks
import aiohttp
import json

class Update(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_events.start()

    @tasks.loop(minutes=5)
    async def update_events(self):
        await self.fetch_and_save_events()
        print("Events updated and saved to events.json")

    @update_events.before_loop
    async def before_update_events(self):
        await self.bot.wait_until_ready()

    @commands.command(name='update')
    async def update_command(self, ctx):
        await self.fetch_and_save_events()
        await ctx.send("Events updated and saved to events.json")

    async def fetch_and_save_events(self):
        guild_id = self.bot.guilds[0].id
        bot_token = self.bot.http.token
        url = f"https://discord.com/api/v9/guilds/{guild_id}/scheduled-events"
        headers = {"Authorization": f"Bot {bot_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    events = await response.json()
                    events_data = [
                        {
                            "event_id": event["id"],
                            "name": event["name"],
                            "scheduled_start_time": event["scheduled_start_time"]
                        }
                        for event in events
                    ]
                    with open('events.json', 'w') as f:
                        json.dump(events_data, f, indent=4)
                else:
                    print(f"Failed to fetch events: {response.status}")

async def setup(bot):
    await bot.add_cog(Update(bot))
    print("Update cog setup complete")
