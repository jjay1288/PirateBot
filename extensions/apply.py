import csv
import json
import asyncio
import re
import os
from datetime import datetime
import interactions
from interactions import (
    Client,
    Extension,
    SlashContext,
    ComponentContext,
    ActionRow,
    StringSelectMenu,
    StringSelectOption,
    Button,
    ButtonStyle,
    listen,
)

# Load the application configuration from JSON
with open('application.json', 'r') as file:
    config = json.load(file)

# Define constants
CSV_FILE = 'applications.csv'

class ApplicationBot(Extension):
    def __init__(self, bot):
        self.bot = bot
        self.applications = {}

    @listen(interactions.events.Ready)
    async def on_ready(self):
        print(f'Logged in as {self.bot.user.username}')

    @listen(interactions.events.MessageCreate)
    async def on_message_create(self, event):
        message = event.message
        user_id = message.author.id
        if user_id in self.applications:
            application = self.applications[user_id]
            dm_channel = application["dm_channel"]
            if message.channel.id == dm_channel.id:
                application["answers"].append(message.content)
                await self.handle_next_question_dm(user_id)

    @interactions.slash_command(
        name="apply",
        description="Start the application process",
        scopes=None
    )
    async def apply_cmd(self, ctx: SlashContext):
        """Start the application process"""
        await ctx.defer(ephemeral=True)  # Defer the original slash command message

        user = ctx.author
        dm_channel = await user.fetch_dm()
        await dm_channel.send(config["messages"]["initial_message"])
        await asyncio.sleep(5)  # Wait for the user to read the initial message

        # Fetch recruiting squadrons
        recruiting_squadrons = [squadron["name"] for squadron in config["squadron_roles"].values() if squadron["recruiting"]]

        # Create the dropdown menu for squadron selection
        squadron_select = StringSelectMenu(
            *[StringSelectOption(label=squadron, value=squadron) for squadron in recruiting_squadrons],
            placeholder="Select a squadron",
            custom_id="squadron_select",
            min_values=1,
            max_values=1
        )
        await dm_channel.send(
            "Which Squadron are you applying to join?",
            components=[ActionRow(squadron_select), ActionRow(Button(style=ButtonStyle.SUCCESS, label="Next", custom_id="next_button"))]
        )
        self.applications[user.id] = {
            "dm_channel": dm_channel,
            "answers": [],
            "current_selection": None,
            "slash_ctx": ctx,
            "username": user.username,
            "start_time": datetime.utcnow()  # Track start time
        }

    @interactions.component_callback("squadron_select")
    async def squadron_select_callback(self, ctx: ComponentContext):
        user_id = ctx.author.id
        self.applications[user_id]["current_selection"] = ctx.values[0]
        await ctx.defer(edit_origin=True)  # Acknowledge the interaction without deleting the message

    @interactions.component_callback("next_button")
    async def next_button_callback(self, ctx: ComponentContext):
        user_id = ctx.author.id
        application = self.applications.get(user_id)
        if application and application["current_selection"] is not None:
            application["answers"].append(application["current_selection"])
            application["current_selection"] = None
        await ctx.defer(edit_origin=True)  # Defer the interaction
        await self.handle_next_question(ctx)

    async def handle_next_question(self, ctx):
        user_id = ctx.author.id
        application = self.applications.get(user_id)
        if not application or len(application["answers"]) == 0:
            await ctx.send("Please select a squadron first.", ephemeral=True)
            return

        answers = application["answers"]
        current_question_index = len(answers)

        if current_question_index < len(config["application_questions"]):
            question = config["application_questions"][current_question_index]
            if question["response_type"] == "dropdown":
                await self.handle_dropdown_question(application["dm_channel"], question, current_question_index)
            elif question["response_type"] == "yes/no":
                await self.handle_yes_no_question(application["dm_channel"], question, current_question_index)
            else:
                await self.handle_text_question(application["dm_channel"], question)
        else:
            self.save_application(user_id, answers, application["username"], application["start_time"])
            await ctx.send('Thank you for your application! The admin team will review your answers and get back to you soon.', ephemeral=True)
            slash_ctx = application.get("slash_ctx")
            if slash_ctx:
                try:
                    await slash_ctx.send("Application completed.", ephemeral=True)  # Complete the original slash command
                except Exception as e:
                    print(f"Error sending completion message: {e}")

    async def handle_dropdown_question(self, dm_channel, question, index):
        select_options = [StringSelectOption(label=opt, value=opt) for opt in question["options"]]
        select = StringSelectMenu(
            *select_options,
            placeholder="Select an option",
            custom_id=f"dropdown_{index}",
            min_values=1,
            max_values=1
        )
        await dm_channel.send(
            question["question"],
            components=[ActionRow(select), ActionRow(Button(style=ButtonStyle.SUCCESS, label="Next", custom_id="next_button"))]
        )

    async def handle_text_question(self, dm_channel, question):
        await dm_channel.send(question["question"])

    async def handle_yes_no_question(self, dm_channel, question, index):
        yes_button = Button(style=ButtonStyle.SUCCESS, label="Yes", custom_id=f"yes_{index}")
        no_button = Button(style=ButtonStyle.DANGER, label="No", custom_id=f"no_{index}")
        await dm_channel.send(
            question["question"],
            components=[ActionRow(yes_button, no_button)]
        )

    async def handle_next_question_dm(self, user_id):
        application = self.applications.get(user_id)
        if not application:
            await application["dm_channel"].send("An error occurred. Please restart the application process.")
            return

        answers = application["answers"]
        current_question_index = len(answers)

        if current_question_index < len(config["application_questions"]):
            question = config["application_questions"][current_question_index]
            if question["response_type"] == "dropdown":
                await self.handle_dropdown_question(application["dm_channel"], question, current_question_index)
            elif question["response_type"] == "yes/no":
                await self.handle_yes_no_question(application["dm_channel"], question, current_question_index)
            else:
                await self.handle_text_question(application["dm_channel"], question)
        else:
            self.save_application(user_id, answers, application["username"])
            await application["dm_channel"].send('Thank you for your application! The admin team will review your answers and get back to you soon.')
            slash_ctx = application.get("slash_ctx")
            if slash_ctx:
                try:
                    await slash_ctx.send("Application completed.", ephemeral=True)  # Complete the original slash command
                except Exception as e:
                    print(f"Error sending completion message: {e}")

    def save_application(self, user_id, answers, username, start_time):
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        # Ensure the CSV file has headers
        file_exists = os.path.isfile(CSV_FILE)
        with open(CSV_FILE, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            headers = [
                "Username", 
                "Which Squadron are you applying to join?", 
                "Requested Callsign", 
                "Are you a member of another DCS Squadron?", 
                "What style of play are you into when playing DCS?", 
                "Are you already an accepted member of HVY?", 
                "Are you a former member of Joint Task Force Heavy?", 
                "Are you over the age of 18?", 
                "Discord Username",
                "User ID", 
                "Status", 
                "Timestamp", 
                "Duration"
            ]
            if not file_exists:
                writer.writerow(headers)

            # Programmatically add Discord Username to the answers
            discord_username = self.bot.get_user(user_id).username
            answers.insert(7, discord_username)  # Insert at the correct position

            # Ensure the order of answers matches the headers
            row = [username] + answers + [str(user_id), "Pending (No Post)", end_time.isoformat(), duration]
            writer.writerow(row)

    @interactions.component_callback(re.compile(r'^dropdown_'))
    async def dropdown_callback(self, ctx: ComponentContext):
        user_id = ctx.author.id
        self.applications[user_id]["current_selection"] = ctx.values[0]
        await ctx.defer(edit_origin=True)  # Acknowledge the interaction without deleting the message

    @interactions.component_callback(re.compile(r'^yes_'))
    async def yes_button_callback(self, ctx: ComponentContext):
        user_id = ctx.author.id
        self.applications[user_id]["answers"].append("Yes")
        if len(self.applications[user_id]["answers"]) < len(config["application_questions"]):
            await ctx.defer(edit_origin=True)  # Defer the interaction if not the last question
        await self.handle_next_question(ctx)

    @interactions.component_callback(re.compile(r'^no_'))
    async def no_button_callback(self, ctx: ComponentContext):
        user_id = ctx.author.id
        self.applications[user_id]["answers"].append("No")
        if len(self.applications[user_id]["answers"]) < len(config["application_questions"]):
            await ctx.defer(edit_origin=True)  # Defer the interaction if not the last question
        await self.handle_next_question(ctx)

def setup(bot):
    ApplicationBot(bot)
