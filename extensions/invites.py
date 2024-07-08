import os
import json
import interactions
from interactions import listen
from interactions.api.events import Ready, GuildJoin, MemberAdd
from config import DEV_GUILD
from src import logutil

logger = logutil.init_logger(os.path.basename(__file__))

INVITE_LOG_FILE = 'invite_log.json'
BOT_CHANNEL_ID = 401633673524543488

class InviteTracker(interactions.Extension):
    def __init__(self, bot):
        self.bot = bot
        logger.debug("Initializing InviteTracker extension...")
        
        # Load or initialize invite log
        if os.path.exists(INVITE_LOG_FILE):
            with open(INVITE_LOG_FILE, 'r') as f:
                self.invite_log = json.load(f)
        else:
            self.invite_log = []

        self.bot.invites = {}
        logger.debug("InviteTracker extension initialized.")

    @listen(Ready)
    async def on_ready(self, event: Ready):
        logger.debug("Bot is ready, fetching invites...")
        for guild in self.bot.guilds:
            invites = await guild.fetch_invites()
            self.bot.invites[guild.id] = {invite.code: invite for invite in invites}
        with open(INVITE_LOG_FILE, 'w') as f:
            json.dump(self.invite_log, f, indent=4)
        logger.debug("Invites fetched and stored.")

    @listen(GuildJoin)
    async def on_guild_join(self, event: GuildJoin):
        guild = event.guild
        logger.debug(f"Joined guild: {guild.name}")

        invites = await guild.fetch_invites()
        self.bot.invites[guild.id] = {invite.code: invite for invite in invites}

    @listen(MemberAdd)
    async def on_guild_member_add(self, event: MemberAdd):
        member = event.member
        logger.debug("Member joined: %s", member.user.username)
        guild_id = member.guild.id
        invites_before_join = self.bot.invites.get(guild_id, {})
        invites_after_join = await member.guild.fetch_invites()

        for invite in invites_after_join:
            if invite.uses > invites_before_join.get(invite.code, invite).uses:
                await self.log_invite(invite, member)
                self.bot.invites[guild_id] = {invite.code: invite for invite in invites_after_join}
                break

    async def log_invite(self, invite, member):
        entry = {
            "code": invite.code,
            "referrer": invite.inviter.username,
            "user": member.user.username,
            "timestamp": member.joined_at.isoformat() if member.joined_at else 'N/A'
        }
        self.invite_log.append(entry)

        with open(INVITE_LOG_FILE, 'w') as f:
            json.dump(self.invite_log, f, indent=4)
        
        # Send message to the bot channel
        bot_channel = await self.bot.fetch_channel(BOT_CHANNEL_ID)
        if bot_channel:
            await bot_channel.send(
                f"New member joined: {member.user.username}\n"
                f"Invite code: {invite.code}\n"
                f"Invited by: {invite.inviter.username}"
            )

    @interactions.slash_command(
        name="invitelog",
        description="Display the last 10 invite codes used with all information",
        scopes=[DEV_GUILD] if DEV_GUILD else None
    )
    async def invitelog_command(self, ctx: interactions.SlashContext):
        logger.debug("invitelog command invoked.")
        if not self.invite_log:
            await ctx.send("No invite logs found.")
            return
        
        messages = [f"**Invite Log:**"]
        for entry in self.invite_log[-10:]:
            messages.append(f"Code: {entry['code']}\n"
                            f"Referrer: {entry['referrer']}\n"
                            f"User: {entry['user']}\n"
                            f"Timestamp: {entry['timestamp']}\n")
        
        await ctx.send('\n'.join(messages))

def setup(bot):
    logger.debug("Setting up InviteTracker extension...")
    InviteTracker(bot)
    logger.debug("InviteTracker extension setup complete")
