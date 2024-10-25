#!/usr/bin/env python3

import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
import json
import asyncio
from quart import Quart, render_template, jsonify

# Load configuration from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

bot_token = config.get("token")
port = config.get("port", 5544)
allowed_roles = config.get("roles", [])
debug = config.get("debug", False)
webserver_enabled = config.get("webserver", False)

# Enable the required intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        # Sync commands with Discord
        await self.tree.sync()

bot = MyBot()

# Debug logging
def log_debug(message):
    if debug:
        print(message)

# Check if user has permission based on roles
def user_has_permission(member: discord.Member):
    if not allowed_roles:  # If no roles are defined, allow everyone
        return True
    for role in member.roles:
        if role.name in allowed_roles:
            log_debug(f"User {member.display_name} allowed: found role {role.name}")
            return True
    log_debug(f"User {member.display_name} not allowed: no matching roles")
    return False

# Helper function to play sound
async def play_sound(sound: str):
    guild = bot.guilds[0] if bot.guilds else None
    voice_client = guild.voice_client if guild else None
    if not voice_client:
        log_debug("Bot is not connected to a voice channel.")
        return

    sound_path = f'sound-clips/{sound}.mp3'
    if not os.path.isfile(sound_path):
        log_debug(f"Sound '{sound}' not found.")
        return

    if voice_client.is_playing():
        voice_client.stop()

    audio_source = discord.FFmpegPCMAudio(sound_path)
    voice_client.play(audio_source)
    log_debug(f"Playing {sound}.mp3")

# Slash command to post controls
@bot.tree.command(name="postcontrols", description="Post buttons to play sound clips")
async def post_controls(interaction: discord.Interaction):
    # Check if the user has permission
    if not user_has_permission(interaction.user):
        await interaction.response.send_message("You don't have permission to use these controls.", ephemeral=True)
        return

    # Get all .mp3 files in the 'sound-clips' directory
    sound_files = [f[:-4] for f in os.listdir('sound-clips') if f.endswith('.mp3')]

    if not sound_files:
        await interaction.response.send_message("No sound files found in the 'sound-clips' directory.")
        return

    # Create a View (container for buttons)
    view = View()

    # Add Join and Leave buttons
    join_button = Button(label="Join", style=discord.ButtonStyle.success)
    leave_button = Button(label="Leave", style=discord.ButtonStyle.danger)

    async def join_callback(interaction: discord.Interaction):
        if interaction.user.voice:
            channel = interaction.user.voice.channel
            await channel.connect()
            if debug:
                await interaction.response.send_message(f"Joined {channel.name}!")
            else:
                await interaction.response.defer()
        else:
            await interaction.response.send_message("You're not connected to a voice channel.", ephemeral=True)

    async def leave_callback(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client:
            await voice_client.disconnect()
            if debug:
                await interaction.response.send_message("Left the voice channel.")
            else:
                await interaction.response.defer()
        else:
            await interaction.response.send_message("I'm not connected to a voice channel.", ephemeral=True)

    join_button.callback = join_callback
    leave_button.callback = leave_callback
    view.add_item(join_button)
    view.add_item(leave_button)

    # Add a button for each sound file
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

    await interaction.response.send_message("Click a button to play a sound:", view=view)

# Quart app setup (for optional web server)
app = Quart(__name__)

@app.route('/')
async def index():
    sounds = [f[:-4] for f in os.listdir('sound-clips') if f.endswith('.mp3')]
    channels = [{"id": ch.id, "name": ch.name} for ch in bot.get_all_channels() if isinstance(ch, discord.VoiceChannel)]
    return await render_template('index.html', sounds=sounds, channels=channels)

@app.route('/play/<sound>')
async def quart_play_sound(sound):
    sound_path = f'sound-clips/{sound}.mp3'
    if os.path.isfile(sound_path):
        guild = bot.guilds[0] if bot.guilds else None
        if guild and guild.voice_client:
            bot.loop.create_task(play_sound(sound))
            return jsonify({"message": f"Playing {sound}"}), 200
        else:
            return jsonify({"error": "Bot is not connected to a voice channel"}), 400
    else:
        return jsonify({"error": "Sound file not found"}), 404

@app.route('/stop')
async def quart_stop_sound():
    guild = bot.guilds[0] if bot.guilds else None
    if guild and guild.voice_client and guild.voice_client.is_playing():
        guild.voice_client.stop()
        return jsonify({"message": "Stopped playing"}), 200
    else:
        return jsonify({"error": "No sound is currently playing"}), 400

@app.route('/join/<channel_id>')
async def quart_join_channel(channel_id):
    guild = bot.guilds[0] if bot.guilds else None
    if guild:
        channel = bot.get_channel(int(channel_id))
        if isinstance(channel, discord.VoiceChannel):
            bot.loop.create_task(channel.connect())
            return jsonify({"message": f"Joined channel {channel.name}"}), 200
        else:
            return jsonify({"error": "Channel not found or not a voice channel"}), 404
    else:
        return jsonify({"error": "Bot is not in any guild"}), 400

@app.route('/leave')
async def quart_leave_channel():
    guild = bot.guilds[0] if bot.guilds else None
    if guild and guild.voice_client:
        bot.loop.create_task(guild.voice_client.disconnect())
        return jsonify({"message": "Left the channel"}), 200
    else:
        return jsonify({"error": "Bot is not connected to a voice channel"}), 400

# Run both the bot and Quart app in the same event loop
async def main():
    await asyncio.gather(
        app.run_task(port=port),
        bot.start(bot_token)
    )

# Run the async main function
asyncio.run(main())
