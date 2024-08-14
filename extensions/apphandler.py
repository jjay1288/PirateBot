import csv
import json
import asyncio
from datetime import datetime
import interactions
import re
import random
import logging
from interactions import Extension, listen, SlashContext, Client, ActionRow, StringSelectMenu, StringSelectOption, Button, ButtonStyle, ComponentContext, slash_command, Embed

CSV_FILE = 'applications.csv'
ANNOUNCEMENT_BODIES_FILE = 'announcement_bodies.json'
APP_HANDLER_CHANNEL_ID = 1135406342224482455
ADMIN_OFFICER_ROLE_ID = 1057490528805077102
GENERAL_ROLE_ID = 400211354654343169
RECRUIT_ROLE_ID = 471107205731450901
ANNOUNCEMENT_CHANNEL_ID = 491080449540751381

with open('application.json', 'r') as file:
    config = json.load(file)

class ApplicationHandler(Extension):
    def __init__(self, bot: Client):
        self.bot = bot

    def get_pending_applications(self):
        pending_applications = []
        try:
            with open(CSV_FILE, 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["Status"] == "Pending":
                        pending_applications.append(row)
        except FileNotFoundError:
            return []

        return pending_applications

    def get_pending_no_post_applications(self):
        no_post_applications = []
        try:
            with open(CSV_FILE, 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["Status"] == "Pending (No Post)":
                        no_post_applications.append(row)
        except FileNotFoundError:
            return []

        return no_post_applications

    def update_application_status(self, user_id, new_status):
        rows = []
        with open(CSV_FILE, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["User ID"] == user_id:
                    row["Status"] = new_status
                rows.append(row)

        with open(CSV_FILE, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    async def check_new_applications(self):
        while True:
            await asyncio.sleep(60)  # Check every minute
            no_post_applications = self.get_pending_no_post_applications()
            for application in no_post_applications:
                user_id = application["User ID"]
                # If the status is "Pending (No Post)", send an alert and update the status to "Pending"
                if application["Status"] == "Pending (No Post)":
                    await self.notify_admins(application)
                    self.update_application_status(user_id, "Pending")

    async def notify_admins(self, application):
        channel = await self.bot.fetch_channel(APP_HANDLER_CHANNEL_ID)
        message = (
            f"New application detected!\n"
            f"Username: {application['Username']}\n"
            f"Application Time: {application['Timestamp']}\n"
            f"To handle this application, use the `/handle` command."
        )
        await channel.send(f"<@&{ADMIN_OFFICER_ROLE_ID}> {message}")

    @slash_command(
        name="handle",
        description="Handle pending applications",
        scopes=[APP_HANDLER_CHANNEL_ID]
    )
    async def handle_cmd(self, ctx: SlashContext):
        if ADMIN_OFFICER_ROLE_ID not in [role.id for role in ctx.author.roles]:
            await ctx.send("You do not have the required permissions to use this command.", ephemeral=True)
            return

        pending_applications = self.get_pending_applications()
        if not pending_applications:
            await ctx.send("No pending applications found.", ephemeral=True)
            return

        options = [
            StringSelectOption(label=app["Username"], value=app["User ID"])
            for app in pending_applications
        ]

        select_menu = StringSelectMenu(
            *options,
            placeholder="Select an application to handle",
            custom_id="application_select",
            min_values=1,
            max_values=1
        )
        await ctx.send(
            "Select an application to handle:",
            components=[ActionRow(select_menu)],
            ephemeral=True
        )

    @listen()
    async def on_ready(self):
        print(f'{self.bot.user.username} is ready and monitoring applications.')
        asyncio.create_task(self.check_new_applications())

    @interactions.component_callback("application_select")
    async def application_select_callback(self, ctx: ComponentContext):
        selected_user_id = ctx.values[0]
        selected_application = None

        with open(CSV_FILE, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["User ID"] == selected_user_id:
                    selected_application = row
                    break

        if selected_application:
            embed = Embed(
                title="Application for Joint Task Force Heavy",
                description=f"Username: {selected_application['Username']}",
                color=0x00ff00
            )
            embed.add_field(name="Which Squadron are you applying to join?", value=selected_application.get('Which Squadron are you applying to join?', 'N/A'), inline=False)
            embed.add_field(name="Requested Callsign", value=selected_application.get('Requested Callsign', 'N/A'), inline=False)
            embed.add_field(name="Are you a member of another DCS Squadron?", value=selected_application.get('Are you a member of another DCS Squadron?', 'N/A'), inline=False)
            embed.add_field(name="What style of play are you into when playing DCS?", value=selected_application.get('What style of play are you into when playing DCS?', 'N/A'), inline=False)
            embed.add_field(name="Are you already an accepted member of HVY?", value=selected_application.get('Are you already an accepted member of HVY?', 'N/A'), inline=False)
            embed.add_field(name="Are you a former member of Joint Task Force Heavy?", value=selected_application.get('Are you a former member of Joint Task Force Heavy?', 'N/A'), inline=False)
            embed.add_field(name="Are you over the age of 18?", value=selected_application.get('Are you over the age of 18?', 'N/A'), inline=False)
            embed.add_field(name="Discord Username", value=selected_application.get('Discord Username', 'N/A'), inline=False)
            embed.add_field(name="User ID", value=selected_application['User ID'], inline=False)
            embed.add_field(name="Username", value=selected_application['Username'], inline=False)
            embed.add_field(name="Status", value=selected_application['Status'], inline=False)
            embed.add_field(name="Timestamp", value=selected_application['Timestamp'], inline=False)
            embed.add_field(name="Duration", value=f"{selected_application.get('Duration', 'N/A')} seconds", inline=False)

            buttons = [
                Button(style=ButtonStyle.SUCCESS, label="Accept", custom_id=f"accept_{selected_user_id}"),
                Button(style=ButtonStyle.DANGER, label="Deny", custom_id=f"deny_{selected_user_id}"),
                Button(style=ButtonStyle.SECONDARY, label="Cancel", custom_id="cancel")
            ]
            await ctx.send(embeds=[embed], components=[ActionRow(*buttons)], ephemeral=True)

    async def get_squadron_leadership(self, guild, squadron_role_id):
        squadron_leadership = {"CO": None, "XO": None}

        # Ensure all members are cached
        await guild.chunk()

        # Get all members in the guild
        squadron_members = guild.members

        for member in squadron_members:
            if squadron_role_id in [r.id for r in member.roles]:
                if member.nick and "[HVY]CO" in member.nick:
                    squadron_leadership["CO"] = member.id
                elif member.nick and "[HVY]XO" in member.nick:
                    squadron_leadership["XO"] = member.id

                if squadron_leadership["CO"] and squadron_leadership["XO"]:
                    break

        return squadron_leadership

    @interactions.component_callback(re.compile(r'^accept_'))
    async def on_accept(self, ctx: ComponentContext):
        user_id = ctx.custom_id.split('_')[1]
        user = await self.bot.fetch_user(user_id)
        guild = await self.bot.fetch_guild(ctx.guild_id)
        member = await guild.fetch_member(user_id)
        
        accept_timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        admin_nickname = ctx.author.nick if ctx.author.nick else ctx.author.username

        # Fetch the user's requested callsign and squadron
        requested_callsign = ""
        squadron_name = ""
        squadron_role_id = None

        with open(CSV_FILE, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["User ID"] == user_id:
                    requested_callsign = row["Requested Callsign"]
                    squadron_name = row["Which Squadron are you applying to join?"]
                    break

        # Assign the squadron role based on the selected squadron
        for role_id, squadron in config["squadron_roles"].items():
            if squadron["name"] == squadron_name:
                squadron_role_id = int(role_id)
                break

        if not squadron_role_id:
            await ctx.send("Squadron role not found for the selected squadron.", ephemeral=True)
            return

        # Change the nickname
        new_nickname = f"[HVY](R){requested_callsign}"
        await member.edit(nickname=new_nickname)

        # Assign the roles
        await member.add_roles([GENERAL_ROLE_ID, RECRUIT_ROLE_ID, squadron_role_id])

        # Create an embed to post in the handler channel
        embed = Embed(
            title="Application Accepted",
            description=f"Application from {user.username} was accepted by {admin_nickname} at {accept_timestamp}. A message notifying the user has been sent.",
            color=0x00ff00
        )

        # Post the embed in the handler channel
        handler_channel = await self.bot.fetch_channel(APP_HANDLER_CHANNEL_ID)
        await handler_channel.send(embeds=[embed])
        
        # Send a DM to the applicant
        dm_message = (
            f"Hello {user.username},\n\n"
            f"Congratulations! Your application to join Joint Task Force Heavy has been accepted. "
            f"Please check the server for further instructions and reach out to a member of HVY leadership if you have any questions.\n\n"
            f"Best regards,\n"
            f"Joint Task Force Heavy Leadership"
        )
        try:
            await user.send(dm_message)
        except Exception as e:
            await handler_channel.send(f"Failed to send DM to {user.username}: {e}")

        # Update the status in the CSV to "Accepted"
        self.update_application_status(user_id, "Accepted")

        # Fetch squadron leadership
        leadership = await self.get_squadron_leadership(guild, squadron_role_id)
        co_mention = f"<@{leadership.get('CO')}>" if leadership.get("CO") else "the CO"
        xo_mention = f"<@{leadership.get('XO')}>" if leadership.get("XO") else "the XO"

        # Load announcement bodies
        with open(ANNOUNCEMENT_BODIES_FILE, 'r') as file:
            announcement_bodies = json.load(file)["announcements"]
        
        # Select a random announcement body
        announcement_body = random.choice(announcement_bodies)

        # Create an announcement
        announcement = (
            f"<@&{GENERAL_ROLE_ID}> Please welcome {user.mention} into the ranks of <@&{squadron_role_id}> under the Command of {co_mention} and {xo_mention}!\n\n"
            f"{announcement_body}"
        )

        # Send the announcement
        announcement_channel = await self.bot.fetch_channel(ANNOUNCEMENT_CHANNEL_ID)
        await announcement_channel.send(announcement)

        await ctx.send(f"Application from User ID {user_id} has been accepted.", ephemeral=True)


    @interactions.component_callback(re.compile(r'^deny_'))
    async def on_deny(self, ctx: ComponentContext):
        user_id = ctx.custom_id.split('_')[1]
        user = await self.bot.fetch_user(user_id)
        deny_timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        admin_nickname = ctx.author.nick if ctx.author.nick else ctx.author.username
        
        # Update the status in the CSV to "Denied"
        self.update_application_status(user_id, "Denied")

        # Create an embed to post in the handler channel
        embed = Embed(
            title="Application Denied",
            description=f"Application from {user.username} was denied by {admin_nickname} at {deny_timestamp}. A message notifying the user has been sent.",
            color=0xff0000
        )

        # Post the embed in the handler channel
        handler_channel = await self.bot.fetch_channel(APP_HANDLER_CHANNEL_ID)
        await handler_channel.send(embeds=[embed])
        
        # Send a DM to the applicant
        dm_message = (
            f"Hello {user.username},\n\n"
            f"Thank you for your application to join Joint Task Force Heavy. After careful consideration, we regret to inform you that your application has been denied. "
            f"If you believe this decision was made in error, please reach out to a member of HVY leadership for further discussion.\n\n"
            f"Best regards,\n"
            f"Joint Task Force Heavy Leadership"
        )
        try:
            await user.send(dm_message)
        except Exception as e:
            await handler_channel.send(f"Failed to send DM to {user.username}: {e}")

        await ctx.send(f"Application from User ID {user_id} has been denied.", ephemeral=True)

    @interactions.component_callback("cancel")
    async def on_cancel(self, ctx: ComponentContext):
        await ctx.send("Operation canceled.", ephemeral=True)

    def checkApp(self, application):
        required_answers = {
            "Are you a member of another DCS Squadron?": "No",
            "Are you already an accepted member of HVY?": "No",
            "Are you a former member of Joint Task Force Heavy? Please explain if YES": "No",
            "Are you over the age of 18?": "Yes"
        }

        for question, required_answer in required_answers.items():
            if application.get(question) != required_answer:
                return False
        return True



def setup(bot):
    ApplicationHandler(bot)
