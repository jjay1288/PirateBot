import json
import discord
from discord.ext import commands
import os

class MyBot(commands.Bot):
    async def setup_hook(self):
        await self.load_extensions()

    async def load_extensions(self):
        print("Loading extensions from ./cogs")
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                print(f"Loading extension: {filename}")
                await self.load_extension(f"cogs.{filename[:-3]}")
        print("Extensions loaded successfully")

async def main():
    print("Loading secrets from client_secrets.json")
    with open('client_secrets.json') as f:
        secrets = json.load(f)
    
    bot_token = secrets['bot_token']
    guild_id = int(secrets['guild_id'])

    print("Creating bot instance")
    intents = discord.Intents.all()
    bot = MyBot(command_prefix='/', intents=intents)

    @bot.event
    async def on_ready():
        print(f'Bot connected as {bot.user} (id: {bot.user.id})')
        guild = discord.utils.get(bot.guilds, id=guild_id)
        if guild:
            print(f'Connected to guild: {guild.name} (id: {guild.id})')
        else:
            print(f'Guild with id {guild_id} not found')

    print("Starting bot...")
    await bot.start(bot_token)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
