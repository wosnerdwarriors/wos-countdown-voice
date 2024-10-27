#!/usr/bin/env python3
import logging
import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
import json
import datetime
import uuid

# Load configuration from config.json
with open("config.json", "r") as config_file:
	config = json.load(config_file)

logging.basicConfig(
	level=logging.DEBUG,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
	handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
global_logs = {}
log_counter = 0  # Counter to generate unique IDs for logs


bot_token = config.get("token")
allowed_roles = config.get("roles-allowed-to-control-bot", [])
purge_channel_ids = config.get("purge-and-repost-on-channel-ids", [])
debug = config.get("debug", True)

# Enable the required intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

class MyBot(commands.Bot):
	def __init__(self):
		super().__init__(command_prefix="!", intents=intents)
		
	async def setup_hook(self):
		try:
			await self.sync_commands()
		except Exception as e:
			logger.exception("Error during command sync.")

	async def sync_commands(self):
		log_message("Attempting to sync commands with Discord...","debug")
		try:
			await self.tree.sync()
			log_message("Commands synced successfully.")
		except Exception as e:
			logger.exception("Error syncing commands")

bot = MyBot()

# Debug logging
def log_message(message, severity="info", category="catchall"):
    global log_counter

    # Increment the log counter for a unique ID
    log_id = log_counter
    log_counter += 1

    # Get the current timestamp
    timestamp = datetime.datetime.now().isoformat()

    # Create the log entry
    log_entry = {
        "id": log_id,
        "timestamp": timestamp,
        "severity": severity,
        "category": category,
        "message": message
    }

    # Store the log entry in global_logs using the log_id as the key
    global_logs[log_id] = log_entry


    # Use the logger to log the message based on severity
    if severity.lower() == "debug":
        logger.debug(message)
    elif severity.lower() == "info":
        logger.info(message)
    elif severity.lower() == "warning":
        logger.warning(message)
    elif severity.lower() == "error":
        logger.error(message)
    elif severity.lower() == "critical":
        logger.critical(message)
    else:
        logger.info(message)  # Default to info if the severity is unknown

    return log_id  # Return the log ID for reference if needed

# Check if user has permission based on roles
def user_has_permission(member: discord.Member):
	log_message(f"Checking permissions for user {member.display_name}", category="user_has_permission")
	if len(allowed_roles) == 0:
		log_message("No specific roles defined, allowing all users.")
		return True
	for role in member.roles:
		if role.name in allowed_roles:
			log_message(f"User {member.display_name} allowed: found role {role.name}", category="user_has_permission")
			return True
	log_message(f"User {member.display_name} not allowed: no matching roles", category="user_has_permission")
	return False

# Helper function to post control buttons
async def post_controls_helper(channel, existing_message=None):
    """Send or update the control message in the specified channel."""
    sound_files = [f[:-4] for f in os.listdir('sound-clips') if f.endswith('.mp3')]

    if not sound_files:
        await channel.send("No sound files found in the 'sound-clips' directory.")
        return

    # Create a View (container for buttons)
    view = View()

    # Add Join, Leave, and Stop buttons
    join_button = Button(label="Join", style=discord.ButtonStyle.success)
    leave_button = Button(label="Leave", style=discord.ButtonStyle.danger)
    stop_button = Button(label="Stop", style=discord.ButtonStyle.danger)

    async def join_callback(interaction: discord.Interaction):
        log_message(f"join_callback called", category="join_callback")
        if interaction.user.voice:
            vc_channel = interaction.user.voice.channel
            log_message(f"join_callback attempting to join the voice channel {vc_channel}", category="join_callback")
            await vc_channel.connect()
            await interaction.response.defer()
        else:
            await interaction.response.send_message("You're not connected to a voice channel.", ephemeral=True)
            log_message(f"join_callback, tried to join a voice channel but the user isn't join to any voice channel so we don't know which one to join", category="join_callback")

    async def leave_callback(interaction: discord.Interaction):
    	log_message(f"leave_callback called", category="leave_callback")
        voice_client = interaction.guild.voice_client
        if voice_client:
        	log_message(f"leave_callback, trying to leave the voice channel {voice_client}", category="leave_callback")
            await voice_client.disconnect()
            await interaction.response.defer()
        else:
            await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)
            log_message(f"leave_callback, tried to leave a voice channel but we're not in any voice channel", category="leave_callback")

    async def stop_callback(interaction: discord.Interaction):
    	log_message(f"stop_callback called", category="stop_callback")
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await interaction.response.send_message("Stopped the current sound.", ephemeral=True)
        else:
            await interaction.response.send_message("No sound is currently playing.", ephemeral=True)

    join_button.callback = join_callback
    leave_button.callback = leave_callback
    stop_button.callback = stop_callback
    view.add_item(join_button)
    view.add_item(leave_button)
    view.add_item(stop_button)

    # Add buttons for each sound file
    for sound in sound_files:
        button = Button(label=sound, style=discord.ButtonStyle.primary)

        async def button_callback(interaction: discord.Interaction, sound=sound):
            if not user_has_permission(interaction.user):
                await interaction.response.send_message("You don't have permission to play this sound.", ephemeral=True)
                return
            await play_sound(sound)
            await interaction.response.defer()

        button.callback = button_callback
        view.add_item(button)

    # Edit the existing message or send a new one
    if existing_message:
        await existing_message.edit(content="Click a button to play a sound:", view=view)
    else:
        await channel.send("Click a button to play a sound:", view=view)

# Helper function to play sound
async def play_sound(sound: str):
	guild = bot.guilds[0] if bot.guilds else None
	voice_client = guild.voice_client if guild else None
	if not voice_client:
		log_message("Bot is not connected to a voice channel.")
		return

	sound_path = f'sound-clips/{sound}.mp3'
	if not os.path.isfile(sound_path):
		log_message(f"Sound '{sound}' not found.")
		return

	if voice_client.is_playing():
		voice_client.stop()

	audio_source = discord.FFmpegPCMAudio(sound_path)
	voice_client.play(audio_source)
	log_message(f"Playing {sound}.mp3")


async def sync_voice_connections():
    """Synchronize the bot's state with existing voice connections."""
    log_message("Synchronizing existing voice connections...")
    for guild in bot.guilds:
        if guild.voice_client:
            log_message(f"Bot is already connected to a voice channel in guild: {guild.name} (ID: {guild.id})")
        else:
            log_message(f"Bot is not connected to any voice channel in guild: {guild.name} (ID: {guild.id})")

@bot.event
async def on_ready():
    log_message(f"{bot.user} has connected to Discord.")
    await sync_voice_connections()  # Synchronize voice connections
    await purge_and_repost_controls()

@bot.event
async def on_guild_join(guild):
	log_message(f"Joined new guild: {guild.name} (ID: {guild.id}). Syncing commands...")
	await bot.sync_commands()

async def purge_and_repost_controls():
    """Edit existing control messages or repost them if needed."""
    log_message(f"Starting purge_and_repost_controls, purge_channel_ids: {purge_channel_ids}")
    for channel_id in purge_channel_ids:
        log_message(f"Processing channel ID: {channel_id}")
        channel = bot.get_channel(channel_id)
        if not channel:
            log_message(f"Channel with ID {channel_id} not found.")
            continue

        # Search for the bot's existing control message in the channel
        existing_message = None
        async for message in channel.history(limit=100):
            if message.author == bot.user:
                existing_message = message
                break

        # Update the existing message or post a new one
        await post_controls_helper(channel, existing_message)

async def main_bot():
	await bot.start(bot_token)

