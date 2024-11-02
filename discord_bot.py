#!/usr/bin/env python3
import logging
import os
import discord
from discord.ext import commands
from discord.ui import Button, View
import json
import datetime

# Load configuration from config.json
with open("config.json", "r") as config_file:
	config = json.load(config_file)

# Configure logging
logging.basicConfig(
	level=logging.DEBUG,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
	handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
global_logs = {}
log_counter = 0  # Counter to generate unique IDs for logs

# Configuration values
bot_token = config.get("token")
allowed_roles = config.get("roles-allowed-to-control-bot", [])
purge_channel_ids = config.get("purge-and-repost-on-channel-ids", [])
debug = config.get("debug", True)

# Enable the required intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

# Helper function to log messages
def log_message(message, severity="info", category="catchall"):
	global log_counter
	log_id = log_counter
	log_counter += 1
	timestamp = datetime.datetime.now().isoformat()
	log_entry = {
		"id": log_id,
		"timestamp": timestamp,
		"severity": severity,
		"category": category,
		"message": message
	}
	global_logs[log_id] = log_entry
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
		logger.info(message)
	return log_id

# Custom log handler to link with global logs
class CustomLogHandler(logging.Handler):
	def emit(self, record):
		message = self.format(record)
		severity = record.levelname.lower()
		log_message(message, severity=severity, category=record.name)

discord_logger = logging.getLogger('discord')
discord_logger.addHandler(CustomLogHandler())
discord_logger.setLevel(logging.DEBUG)

# Define the bot class
class MyBot(commands.Bot):
	def __init__(self):
		super().__init__(command_prefix="!", intents=intents)
	
	async def setup_hook(self):
		log_message("setup_hook called", category="setup_hook")
		try:
			await self.sync_commands()
		except Exception as e:
			log_message(f"Error during command sync: {str(e)}", severity="error", category="setup_hook")
			logger.exception("Error during command sync.")

	async def sync_commands(self):
		log_message("Attempting to sync commands with Discord...", "debug", category="sync_commands")
		try:
			await self.tree.sync()
			log_message("Commands synced successfully.", category="sync_commands")
		except Exception as e:
			log_message(f"Error syncing commands: {str(e)}", severity="error", category="sync_commands")
			logger.exception("Error syncing commands")

bot = MyBot()

# Slash command to post control buttons
@bot.tree.command(name="postcontrols", description="Post the control buttons in the current channel")
async def post_controls(interaction: discord.Interaction):
	"""Slash command to post the control buttons in the current channel."""
	log_message(f"Received /postcontrols command from user {interaction.user.display_name} in channel {interaction.channel.name}", category="post_controls")
	await post_controls_helper(interaction.channel)
	await interaction.response.send_message("Control buttons posted successfully.", ephemeral=True)
	log_message("Control buttons posted successfully.", category="post_controls")

# Helper function to check user permissions
def user_has_permission(member: discord.Member):
	log_message(f"Checking permissions for user {member.display_name}", category="user_has_permission")
	if not allowed_roles:
		log_message("No specific roles defined, allowing all users.", category="user_has_permission")
		return True
	for role in member.roles:
		if role.name in allowed_roles:
			log_message(f"User {member.display_name} allowed: found role {role.name}", category="user_has_permission")
			return True
	log_message(f"User {member.display_name} not allowed: no matching roles", category="user_has_permission")
	return False

# Persistent view for control buttons
class ControlView(View):
    def __init__(self):
        super().__init__(timeout=None)  # Set timeout to None for persistence

        # Add persistent Join, Leave, and Stop buttons
        join_button = Button(label="Join", style=discord.ButtonStyle.success, custom_id="join_button")
        leave_button = Button(label="Leave", style=discord.ButtonStyle.danger, custom_id="leave_button")
        stop_button = Button(label="Stop", style=discord.ButtonStyle.danger, custom_id="stop_button")

        join_button.callback = self.join_callback
        leave_button.callback = self.leave_callback
        stop_button.callback = self.stop_callback

        self.add_item(join_button)
        self.add_item(leave_button)
        self.add_item(stop_button)

        # Add buttons for each sound file
        sound_files = [f[:-4] for f in os.listdir('sound-clips') if f.endswith('.mp3')]
        for sound in sound_files:
            button = Button(label=sound, style=discord.ButtonStyle.primary, custom_id=f"sound_{sound}")
            button.callback = lambda interaction, sound=sound: self.play_sound_callback(interaction, sound)
            self.add_item(button)

    async def join_callback(self, interaction: discord.Interaction):
        log_message("join_callback called", category="join_callback")
        if interaction.user.voice:
            vc_channel = interaction.user.voice.channel
            log_message(f"Attempting to join the voice channel {vc_channel}", category="join_callback")
            await vc_channel.connect()
            log_message("Successfully connected to the voice channel.", category="join_callback")
            await interaction.response.defer()
        else:
            await interaction.response.send_message("You're not connected to a voice channel.", ephemeral=True)
            log_message("User not connected to a voice channel.", category="join_callback")

    async def leave_callback(self, interaction: discord.Interaction):
        log_message("leave_callback called", category="leave_callback")
        voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
        if voice_client:
            log_message(f"Leaving the voice channel {voice_client.channel}", category="leave_callback")
            await voice_client.disconnect()
            await interaction.response.defer()
        else:
            await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)
            log_message("No voice channel to leave.", category="leave_callback")

    async def stop_callback(self, interaction: discord.Interaction):
        log_message("stop_callback called", category="stop_callback")
        await stop_sound(interaction.guild)
        await interaction.response.send_message("Stopped the current sound.", ephemeral=True)

    async def play_sound_callback(self, interaction: discord.Interaction, sound: str):
        log_message(f"play_sound_callback called for sound: {sound}", category="play_sound_callback")
        if not user_has_permission(interaction.user):
            await interaction.response.send_message("You don't have permission to play this sound.", ephemeral=True)
            log_message(f"User {interaction.user.display_name} does not have permission to play {sound}.", category="play_sound_callback")
            return

        await play_sound(sound, interaction.guild)
        await interaction.response.defer()

# Register the view with the bot
@bot.event
async def on_ready():
    log_message(f"{bot.user} has connected to Discord.", category="on_ready")
    bot.add_view(ControlView())  # Register the ControlView for persistence
    await cleanup_orphaned_voice_connections()
    await sync_voice_connections()
    await purge_and_repost_controls()


# Helper function to post control buttons in a channel
async def post_controls_helper(channel, existing_message=None):
	log_message(f"post_controls_helper called for channel: {channel}", category="post_controls_helper")
	view = ControlView()

	if existing_message:
		await existing_message.edit(content="Click a button to play a sound:", view=view)
		log_message(f"Edited existing control message {existing_message}.", category="post_controls_helper")
	else:
		await channel.send("Controls for wos countdown:", view=view)
		log_message(f"Posted new control message in channel {channel}.", category="post_controls_helper")

# Function to play sound
async def play_sound(sound: str, guild: discord.Guild):
	log_message(f"play_sound called with sound: {sound}", category="play_sound")
	voice_client = discord.utils.get(bot.voice_clients, guild=guild)
	if not voice_client:
		log_message("Bot is not connected to a voice channel.", severity="warning", category="play_sound")
		return

	sound_path = f'sound-clips/{sound}.mp3'
	if not os.path.isfile(sound_path):
		log_message(f"Sound '{sound}' not found.", severity="error", category="play_sound")
		return

	if voice_client.is_playing():
		voice_client.stop()
		log_message("Stopped the currently playing sound.", category="play_sound")

	audio_source = discord.FFmpegPCMAudio(sound_path)
	voice_client.play(audio_source)
	log_message(f"Playing {sound}.mp3", category="play_sound")

# Function to stop sound
async def stop_sound(guild: discord.Guild):
	log_message("stop_sound called", category="stop_sound")
	voice_client = discord.utils.get(bot.voice_clients, guild=guild)
	if voice_client and voice_client.is_playing():
		voice_client.stop()
		log_message("Sound stopped successfully.", category="stop_sound")
	else:
		log_message("No sound is currently playing.", category="stop_sound")

# Function to synchronize existing voice connections
async def sync_voice_connections():
	log_message(f"sync_voice_connections being called")
	log_message("Synchronizing existing voice connections...", category="sync_voice_connections")
	for guild in bot.guilds:
		voice_client = discord.utils.get(bot.voice_clients, guild=guild)
		if voice_client:
			log_message(f"sync_voice_connections Bot is already connected to a voice channel in guild: {guild.name} (ID: {guild.id})", category="sync_voice_connections")
		else:
			log_message(f" sync_voice_connections Bot is not connected to any voice channel in guild: {guild.name} (ID: {guild.id})", category="sync_voice_connections")

# Function to clean up any orphaned voice connections
async def cleanup_orphaned_voice_connections():
	log_message("Running cleanup for orphaned voice connections...", category="cleanup_orphaned_voice_connections")
	for guild in bot.guilds:
		voice_client = discord.utils.get(bot.voice_clients, guild=guild)
		if not voice_client and guild.voice_client:
			try:
				log_message(f"Detected an orphaned voice connection in guild: {guild.name} (ID: {guild.id}). Attempting to disconnect.", category="cleanup_orphaned_voice_connections")
				await guild.voice_client.disconnect(force=True)
				log_message(f"Successfully disconnected from an orphaned voice channel in guild: {guild.name} (ID: {guild.id})", category="cleanup_orphaned_voice_connections")
			except Exception as e:
				log_message(f"Failed to disconnect from orphaned voice channel in guild: {guild.name} (ID: {guild.id}): {str(e)}", severity="error", category="cleanup_orphaned_voice_connections")

@bot.event
async def on_ready():
    log_message(f"{bot.user} has connected to Discord.", category="on_ready")
    bot.add_view(ControlView())  # Register the ControlView for persistence
    await cleanup_orphaned_voice_connections()
    await sync_voice_connections()
    await purge_and_repost_controls()

 
@bot.event
async def on_guild_join(guild):
	log_message(f"Joined new guild: {guild.name} (ID: {guild.id}). Syncing commands...", category="on_guild_join")
	await bot.sync_commands()

# Function to purge and repost control buttons
async def purge_and_repost_controls():
	log_message(f"Starting purge_and_repost_controls, purge_channel_ids: {purge_channel_ids}", category="purge_and_repost_controls")
	for channel_id in purge_channel_ids:
		channel = bot.get_channel(channel_id)
		if not channel:
			log_message(f"Channel with ID {channel_id} not found.", category="purge_and_repost_controls")
			continue

		existing_message = None
		async for message in channel.history(limit=100):
			if message.author == bot.user:
				existing_message = message
				break

		await post_controls_helper(channel, existing_message)

async def main_bot():
	await bot.start(bot_token)
