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

# Helper function to post control buttons in a channel
# Helper function to post control buttons in a channel
async def post_controls_helper(channel, existing_message=None):
	log_message(f"post_controls_helper called for channel: {channel}", category="post_controls_helper")
	sound_files = [f[:-4] for f in os.listdir('sound-clips') if f.endswith('.mp3')]

	if not sound_files:
		await channel.send("No sound files found in the 'sound-clips' directory.")
		log_message("No sound files found to post controls.", category="post_controls_helper")
		return

	view = View()

	# Add Join, Leave, and Stop buttons
	join_button = Button(label="Join", style=discord.ButtonStyle.success)
	leave_button = Button(label="Leave", style=discord.ButtonStyle.danger)
	stop_button = Button(label="Stop", style=discord.ButtonStyle.danger)

	async def join_callback(interaction: discord.Interaction):
		log_message("join_callback called", category="join_callback")
		if interaction.user.voice:
			vc_channel = interaction.user.voice.channel
			log_message(f"Attempting to join the voice channel {vc_channel}", category="join_callback")
			voice_client = await vc_channel.connect()
			log_message("Successfully connected to the voice channel.", category="join_callback")
			await interaction.response.defer()
		else:
			await interaction.response.send_message("You're not connected to a voice channel.", ephemeral=True)
			log_message("User not connected to a voice channel.", category="join_callback")

	async def leave_callback(interaction: discord.Interaction):
		log_message("leave_callback called", category="leave_callback")
		voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
		if voice_client:
			log_message(f"Leaving the voice channel {voice_client.channel}", category="leave_callback")
			await voice_client.disconnect()
			await interaction.response.defer()
		else:
			await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)
			log_message("No voice channel to leave.", category="leave_callback")

	async def stop_callback(interaction: discord.Interaction):
		log_message("stop_callback called", category="stop_callback")
		voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
		if voice_client and voice_client.is_playing():
			log_message("Stopping the current sound.", category="stop_callback")
			voice_client.stop()
			await interaction.response.send_message("Stopped the current sound.", ephemeral=True)
		else:
			await interaction.response.send_message("No sound is currently playing.", ephemeral=True)
			log_message("No sound to stop.", category="stop_callback")

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
			log_message(f"Button pressed to play sound: {sound}", category="button_callback")
			if not user_has_permission(interaction.user):
				await interaction.response.send_message("You don't have permission to play this sound.", ephemeral=True)
				log_message(f"User {interaction.user.display_name} does not have permission to play {sound}.", category="button_callback")
				return

			voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
			if not voice_client:
				await interaction.response.send_message("Bot is not connected to a voice channel. Please use the 'Join' button first.", ephemeral=True)
				log_message("Attempt to play sound failed: Bot is not connected to a voice channel.", severity="warning", category="button_callback")
				return

			sound_path = f'sound-clips/{sound}.mp3'
			if not os.path.isfile(sound_path):
				log_message(f"Sound '{sound}' not found.", severity="error", category="button_callback")
				await interaction.response.send_message(f"Sound '{sound}' not found.", ephemeral=True)
				return

			if voice_client.is_playing():
				voice_client.stop()
				log_message("Stopped the currently playing sound.", category="button_callback")

			audio_source = discord.FFmpegPCMAudio(sound_path)
			voice_client.play(audio_source)
			log_message(f"Playing {sound}.mp3", category="button_callback")
			await interaction.response.defer()

		button.callback = button_callback
		view.add_item(button)

	if existing_message:
		await existing_message.edit(content="Click a button to play a sound:", view=view)
		log_message(f"Edited existing control message {existing_message}.", category="post_controls_helper")
	else:
		await channel.send("Controls for wos countdown:", view=view)
		log_message(f"Posted new control message in channel {channel}.", category="post_controls_helper")


# Helper function to play sound
async def play_sound(sound: str):
	log_message(f"play_sound called with sound: {sound}", category="play_sound")
	guild = bot.guilds[0] if bot.guilds else None
	voice_client = guild.voice_client if guild else None
	if not voice_client:
		log_message("Bot is not connected to a voice channel.", severity="warning", category="play_sound")
		return

	sound_path = f'sound-clips/{sound}.mp3'
	if not os.path.isfile(sound_path):
		log_message(f"Sound '{sound}' not found.", severity="error", category="play_sound")
		return

	if voice_client.is_playing():
		voice_client.stop()
		log_message(f"Stopped the currently playing sound.", category="play_sound")

	audio_source = discord.FFmpegPCMAudio(sound_path)
	voice_client.play(audio_source)
	log_message(f"Playing {sound}.mp3", category="play_sound")

async def sync_voice_connections():
	log_message("Synchronizing existing voice connections...", category="sync_voice_connections")
	for guild in bot.guilds:
		if guild.voice_client:
			log_message(f"Bot is already connected to a voice channel in guild: {guild.name} (ID: {guild.id})", category="sync_voice_connections")
		else:
			log_message(f"Bot is not connected to any voice channel in guild: {guild.name} (ID: {guild.id})", category="sync_voice_connections")

@bot.event
async def on_ready():
	log_message(f"{bot.user} has connected to Discord.", category="on_ready")
	await sync_voice_connections()
	await purge_and_repost_controls()

@bot.event
async def on_guild_join(guild):
	log_message(f"Joined new guild: {guild.name} (ID: {guild.id}). Syncing commands...", category="on_guild_join")
	await bot.sync_commands()

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
