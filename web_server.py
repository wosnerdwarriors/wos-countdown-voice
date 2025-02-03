from quart import Quart, jsonify, request, render_template
import os
import logging
import asyncio
from discord_bot import bot, play_sound, global_logs, log_message
import discord
import json

logger = logging.getLogger(__name__)

# Load configuration from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

# Get the web server port from the configuration, with a default fallback
webserver_port = config.get("webserver-port", 5544)

app = Quart(__name__)
app.config['DEBUG'] = True
app.config["PROVIDE_AUTOMATIC_OPTIONS"] = True  # Add this line to prevent the KeyError

@app.route('/')
async def index():
	sounds = [f[:-4] for f in os.listdir('sound-clips') if f.endswith('.mp3')]
	guilds = [
		{"name": guild.name, "channels": [{"id": ch.id, "name": ch.name} for ch in guild.channels if isinstance(ch, discord.VoiceChannel)]}
		for guild in bot.guilds
	]
	return await render_template('index.html', sounds=sounds, guilds=guilds)

@app.route('/api/sounds')
async def get_sounds():
	sound_files = [f[:-4] for f in os.listdir('sound-clips') if f.endswith('.mp3')]
	return jsonify(sound_files)

@app.route('/api/guilds')
async def get_guilds():
	guilds = [
		{"id": str(guild.id), "name": guild.name} for guild in bot.guilds
	]
	return jsonify(guilds)

@app.route('/api/channels/<guild_id>')
async def get_channels(guild_id):
	try:
		guild_id = int(guild_id)
	except ValueError:
		return jsonify({"error": "Invalid guild ID"}), 400

	guild = discord.utils.get(bot.guilds, id=guild_id)
	if guild:
		channels = [{"id": str(ch.id), "name": ch.name} for ch in guild.channels if isinstance(ch, discord.VoiceChannel)]
		return jsonify(channels)
	else:
		return jsonify({"error": "Guild not found"}), 404

@app.route('/api/join', methods=['POST'])
async def join_channel():
	data = await request.get_json()
	guild_id = int(data.get("guildId"))
	channel_id = int(data.get("channelId"))

	guild = discord.utils.get(bot.guilds, id=guild_id)
	if not guild:
		return jsonify({"error": "Guild not found"}), 404

	channel = discord.utils.get(guild.channels, id=channel_id)
	if not channel or not isinstance(channel, discord.VoiceChannel):
		return jsonify({"error": "Voice channel not found"}), 404

	await channel.connect()
	return jsonify({"message": f"Joined channel {channel.name} in guild {guild.name}"}), 200

@app.route('/api/play', methods=['POST'])
async def play_sound_api():
	data = await request.get_json()
	guild_id = int(data.get("guildId"))
	sound = data.get("sound")

	guild = discord.utils.get(bot.guilds, id=guild_id)
	if not guild:
		return jsonify({"error": "Guild not found"}), 404

	voice_client = guild.voice_client
	if not voice_client:
		return jsonify({"error": "Bot is not connected to a voice channel"}), 400

	sound_path = f'sound-clips/{sound}.mp3'
	if not os.path.isfile(sound_path):
		return jsonify({"error": "Sound file not found"}), 404

	if voice_client.is_playing():
		voice_client.stop()

	audio_source = discord.FFmpegPCMAudio(sound_path)
	voice_client.play(audio_source)
	return jsonify({"message": f"Playing {sound}.mp3 in {voice_client.channel.name}"}), 200

# API to fetch all log messages, optionally starting from a specified log ID
@app.route('/api/logs', methods=['GET'])
async def get_all_logs():
    # Get the last_log_id parameter from the query string
    last_log_id = request.args.get('last_log_id', type=int, default=None)

    # Filter logs based on the last_log_id if provided
    if last_log_id is not None:
        filtered_logs = {log_id: log_entry for log_id, log_entry in global_logs.items() if log_id > last_log_id}
    else:
        filtered_logs = global_logs  # Return all logs if no last_log_id is specified

    # Return the filtered logs
    return jsonify(filtered_logs)


async def main_web():
    await app.run_task(port=webserver_port)