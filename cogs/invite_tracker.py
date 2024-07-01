import discord
from discord.ext import commands
import json
import os
import aiohttp

class InviteTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invites = {}
        self.load_invites()

    def load_invites(self):
        print("Checking if invites.json exists...")
        if os.path.exists('invites.json'):
            print("invites.json found. Loading invites...")
            with open('invites.json', 'r') as f:
                self.invites = json.load(f)
            print("Invites loaded successfully.")
        else:
            print("invites.json not found. Initializing empty invites.")
            self.invites = {}

    def save_invites(self):
        print("Saving invites to invites.json...")
        with open('invites.json', 'w') as f:
            json.dump(self.invites, f, indent=4)
        print("Invites saved successfully.")

    @commands.command(name='getinvites')
    async def getinvites_command(self, ctx):
        await self.fetch_all_invites()
        await ctx.send("Invites have been updated and saved to invites.json")

    async def fetch_all_invites(self):
        print("Fetching all invites...")
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                for invite in invites:
                    self.invites[invite.code] = {
                        'inviter': invite.inviter.name,
                        'uses': invite.uses,
                        'max_uses': invite.max_uses,
                        'created_at': str(invite.created_at)
                    }
            except Exception as e:
                print(f"Error fetching invites for guild {guild.name}: {e}")
        self.save_invites()

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        print(f"New invite created: {invite.code}")
        self.invites[invite.code] = {
            'inviter': invite.inviter.name,
            'uses': invite.uses,
            'max_uses': invite.max_uses,
            'created_at': str(invite.created_at)
        }
        self.save_invites()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        print(f"Member joined: {member.name}")
        try:
            guild_invites = await member.guild.invites()
            for invite in guild_invites:
                if invite.code in self.invites and invite.uses > self.invites[invite.code]['uses']:
                    self.invites[invite.code]['uses'] = invite.uses
                    self.invites[invite.code]['last_used_by'] = member.name
                    self.save_invites()
                    print(f"Invite {invite.code} used by {member.name}. Updated invite info.")
                    break
        except Exception as e:
            print(f"Error updating invites on member join for {member.name}: {e}")

    @commands.command(name='lastinvite')
    async def lastinvite_command(self, ctx):
        print("Processing lastinvite command...")
        last_invite = None
        for invite in self.invites.values():
            if 'last_used_by' in invite:
                last_invite = invite
                break

        if last_invite:
            await ctx.send(f"Last invite used by: {last_invite['last_used_by']} (Inviter: {last_invite['inviter']})")
        else:
            await ctx.send("No invites have been used yet.")
        print("lastinvite command processed.")

async def setup(bot):
    await bot.add_cog(InviteTracker(bot))
    print("InviteTracker cog setup complete")
