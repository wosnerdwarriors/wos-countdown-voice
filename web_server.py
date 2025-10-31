from quart import Quart, jsonify, request, render_template, send_file
import os
import logging
import asyncio
import contextlib
from discord_bot import bot, play_sound, global_logs, log_message, stop_sound
from rally_audio import audio_scheduler
import discord
import json
from rally_store import rally_store, DataValidationError
from pydub import AudioSegment
import re
import tempfile
from gtts import gTTS
import pyttsx3
from config_enums import DebugSection, is_debug_section_enabled

logger = logging.getLogger(__name__)

# Load configuration from config.json
with open("config.json", "r") as config_file:
    config = json.load(config_file)

RUNNING_IN_DOCKER = os.getenv("RUNNING_IN_DOCKER", "false").lower() == "true"

DEFAULT_PORT = 5544 
DEFAULT_HOST = "127.0.0.1" # when not using docker

# Set webserver port:
if RUNNING_IN_DOCKER:
    webserver_port = DEFAULT_PORT  # Always 5544 in Docker
else:
    webserver_port = config.get("webserver-port", DEFAULT_PORT)  # Use config, fallback to 5544

# Set webserver host:
if RUNNING_IN_DOCKER:
    webserver_host = "0.0.0.0"  # Always 0.0.0.0 in Docker
else:
    webserver_host = config.get("webserver-host", DEFAULT_HOST)  # Use config, fallback to 127.0.0.1


app = Quart(__name__)


def is_debug_enabled(section=None):
	return is_debug_section_enabled(config, section)

app.config['DEBUG'] = is_debug_enabled(DebugSection.WEB)
app.config["PROVIDE_AUTOMATIC_OPTIONS"] = True  # Add this line to prevent the KeyError
# readiness event set by before_serving hook
web_ready: asyncio.Event = asyncio.Event()
# Optional shutdown event that callers (like main.py) can set to request
# Hypercorn to stop via the shutdown_trigger. If None, `main_web` will
# create one for its own use and assign it here so callers can access it.
web_shutdown_event: asyncio.Event | None = None

class _HypercornTrafficFilter(logging.Filter):
	"""Filter out routine HTTP request logs unless web_access debugging is enabled."""

	_methods = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD")

	def filter(self, record: logging.LogRecord) -> bool:
		if is_debug_enabled(DebugSection.WEB_ACCESS):
			return True
		msg = record.getMessage()
		if not msg:
			return True
		return not any(f"{method} /" in msg for method in self._methods)

_hypercorn_access_logger = logging.getLogger("hypercorn.access")
_hypercorn_access_logger.propagate = False
_hypercorn_access_logger.addFilter(_HypercornTrafficFilter())
if is_debug_enabled(DebugSection.WEB_ACCESS):
	_hypercorn_access_logger.disabled = False
	_hypercorn_access_logger.setLevel(logging.INFO)
else:
	_hypercorn_access_logger.disabled = True

_hypercorn_error_logger = logging.getLogger("hypercorn.error")
_hypercorn_error_logger.propagate = False
_hypercorn_error_logger.addFilter(_HypercornTrafficFilter())
# Ensure Hypercorn error/info logs are available at INFO level so the
# standard "Running on http://... (CTRL + C to quit)" message is visible
# on server startup even when web access debugging is disabled.
_hypercorn_error_logger.disabled = False
_hypercorn_error_logger.setLevel(logging.INFO)

@app.route('/')
async def index():
	sounds = [f[:-4] for f in os.listdir('sound-clips') if f.endswith('.mp3')]
	guilds = [
		{"name": guild.name, "channels": [{"id": ch.id, "name": ch.name} for ch in guild.channels if isinstance(ch, discord.VoiceChannel)]}
		for guild in bot.guilds
	]
	return await render_template('index.html', sounds=sounds, guilds=guilds)

@app.route('/sounds')
async def sounds_management():
	return await render_template('sounds.html')

@app.route('/rally')
async def rally_page():
	return await render_template('rally.html')

# --------------- Audio Scheduler Endpoints ---------------

@app.before_serving
async def startup_audio_scheduler():
	# ensure scheduler loop started
	await audio_scheduler.start()


@app.before_serving
async def _signal_ready():
	"""Signal that the Quart app has reached its before_serving stage (ready to accept requests)."""
	try:
		# Notify readiness for in-process callers
		web_ready.set()
		# Emit a startup/info message similar to Hypercorn's usual output so
		# users see the listening URL in the console. Use the hypercorn.error
		# logger at INFO level to mimic the previous behavior.
		try:
			msg = f"Running on http://{webserver_host}:{webserver_port} (CTRL + C to quit)"
			# Print a short process-style line (timestamp + pid) to stdout as the
			# gunicorn/hypercorn runner did previously. Keep this minimal.
			print(msg)
			_hypercorn_error_logger.info(msg)
		except Exception:
			# Fallback to module logger
			logger.info(f"Web ready on {webserver_host}:{webserver_port}")
	except Exception:
		logger.exception("Failed to set web_ready event")

@app.route('/api/rally/audio', methods=['GET'])
async def audio_state():
	state = await audio_scheduler.get_state()
	return jsonify(state)

@app.route('/api/rally/audio/config', methods=['POST'])
async def audio_update_config():
	data = await request.get_json(force=True)
	# allow partial fields including prefix configuration
	fields = {}
	for k in ('enabled','sound_name','lead_seconds','offset_ms','guild_id','channel_id','prefix_sound_name','prefix_advance_seconds'):
		if k in data:
			fields[k] = data[k]
	# normalize types
	if 'enabled' in fields:
		fields['enabled'] = bool(fields['enabled'])
	if 'lead_seconds' in fields:
		try: fields['lead_seconds'] = int(fields['lead_seconds'])
		except: fields['lead_seconds'] = 0
	if 'offset_ms' in fields:
		try: fields['offset_ms'] = int(fields['offset_ms'])
		except: fields['offset_ms'] = 0
	if 'prefix_advance_seconds' in fields:
		try: fields['prefix_advance_seconds'] = int(fields['prefix_advance_seconds'])
		except: fields['prefix_advance_seconds'] = 0
	await audio_scheduler.update_config(**fields)
	return jsonify({"ok": True})

@app.route('/api/rally/audio/adjust', methods=['POST'])
async def audio_adjust_offset():
	data = await request.get_json(force=True)
	delta_ms = int((data or {}).get('delta_ms', 0))
	await audio_scheduler.adjust_offset_ms(delta_ms)
	return jsonify({"ok": True})

@app.route('/api/rally/audio/trigger', methods=['POST'])
async def audio_trigger_now():
	ok = await audio_scheduler.trigger_now()
	return jsonify({"ok": bool(ok)})

@app.route('/api/rally/audio/connect', methods=['POST'])
async def audio_connect():
	ok = await audio_scheduler.ensure_connected()
	return jsonify({"ok": bool(ok)})

@app.route('/api/rally/audio/stop', methods=['POST'])
async def audio_stop():
	state = await audio_scheduler.get_state()
	gid = state.get('guild_id')
	if not gid:
		return jsonify({"ok": False, "error": "no guild configured"})
	try:
		guild = discord.utils.get(bot.guilds, id=int(gid))
		if not guild:
			return jsonify({"ok": False, "error": "guild not found"})
		await stop_sound(guild)
		return jsonify({"ok": True})
	except Exception as e:
		return jsonify({"ok": False, "error": str(e)})

@app.route('/api/sounds')
async def get_sounds():
	items = []
	for f in os.listdir('sound-clips'):
		if not f.endswith('.mp3'): continue
		path = os.path.join('sound-clips', f)
		try:
			size = os.path.getsize(path)
		except Exception:
			size = 0
		items.append({"name": f[:-4], "filename": f, "bytes": size})
	return jsonify(items)

# ---------- Sound Management Utilities ----------
SAFE_PREFIX = "gen_"
SAFE_SUFFIX = ""
SAFE_PATTERN = re.compile(r'[^a-zA-Z0-9_-]+')

def sanitize_basename(name: str) -> str:
	name = name.strip().lower()
	name = SAFE_PATTERN.sub('-', name)
	name = name.strip('-_')
	if not name:
		name = 'untitled'
	# enforce prefix/suffix
	if not name.startswith(SAFE_PREFIX):
		name = SAFE_PREFIX + name
	if SAFE_SUFFIX and not name.endswith(SAFE_SUFFIX):
		name = name + SAFE_SUFFIX
	return name[:60]  # length cap


def _abs_sound_path(fname: str) -> str | None:
	"""Return absolute path to sound file if it's safely located under sound-clips,
	otherwise return None. This prevents directory traversal.
	"""
	base_dir = os.path.abspath('sound-clips')
	# Normalize and join
	candidate = os.path.normpath(os.path.join('sound-clips', fname))
	try:
		cand_abs = os.path.abspath(candidate)
	except Exception:
		return None
	# Ensure candidate is under base_dir
	try:
		if os.path.commonpath([base_dir, cand_abs]) != base_dir:
			return None
	except Exception:
		return None
	return cand_abs


def _client_ip():
	# Best-effort client IP for rate-limiting; may be proxied in production.
	try:
		return request.remote_addr or 'unknown'
	except Exception:
		return 'unknown'

# Simple in-memory rate limiter: per-endpoint, per-IP counters reset every minute
_rate_limits: dict[tuple[str, str], dict[str, float]] = {}
def _rate_allow(key: str, ip: str, limit: int = 5, window_seconds: int = 60) -> bool:
	now = time.time()
	rec = _rate_limits.get((key, ip))
	if not rec:
		_rate_limits[(key, ip)] = {'count': 1, 'ts': now}
		return True
	if now - rec['ts'] > window_seconds:
		rec['count'] = 1
		rec['ts'] = now
		return True
	if rec['count'] >= limit:
		return False
	rec['count'] += 1
	return True

def ensure_sound_dir():
	if not os.path.isdir('sound-clips'):
		os.makedirs('sound-clips', exist_ok=True)

def generate_countdown_sound(start: int, end: int, language: str, basename: str):
	# mimic logic from generate-countdown.py but simplified
	from gtts import gTTS
	from pydub import AudioSegment
	ensure_sound_dir()
	tmp_dir = 'tmp-data'
	os.makedirs(tmp_dir, exist_ok=True)
	combined = AudioSegment.silent(duration=0)
	segments = {}
	durations = []
	for i in range(start, end-1, -1):
		tts = gTTS(text=str(i), lang=language)
		tmp_path = os.path.join(tmp_dir, f"{basename}-{i}.mp3")
		tts.save(tmp_path)
		seg = AudioSegment.from_mp3(tmp_path)
		durations.append(len(seg))
		segments[i] = seg
	max_dur = max(durations) if durations else 1000
	speed_factor = max_dur / 1000.0
	for i in range(start, end-1, -1):
		seg = segments[i]
		seg = seg.speedup(playback_speed=speed_factor)
		if len(seg) < 1000:
			seg += AudioSegment.silent(duration=1000-len(seg))
		combined += seg
	out_path = os.path.join('sound-clips', f"{basename}.mp3")
	combined.export(out_path, format='mp3')
	return out_path

def generate_tts_sound(text: str, voice_idx: int|None, max_seconds: float|None, basename: str,
					 engine_choice: str = 'system', rate: int|None = None, volume: float|None = None, gtts_lang: str|None = 'en'):
	"""Generate a TTS sound via either system voices (pyttsx3) or gTTS.

	Arguments:
		text: phrase to synthesize
		voice_idx: index into system voices (only for engine_choice == 'system')
		max_seconds: if provided and system synthesis exceeds, speed up audio to fit
		basename: sanitized base filename (without extension)
		engine_choice: 'system' or 'gtts'
		rate: optional pyttsx3 rate override (int)
		volume: optional pyttsx3 volume (0.0-1.0)
		gtts_lang: language code for gTTS
	"""
	ensure_sound_dir()
	engine_choice = (engine_choice or 'system').lower()
	if engine_choice == 'gtts':
		lang = gtts_lang or 'en'
		try:
			t = gTTS(text=text, lang=lang)
			out_path = os.path.join('sound-clips', f"{basename}.mp3")
			t.save(out_path)
			return out_path
		except Exception:
			# fall back to system if gTTS fails
			engine_choice = 'system'
	# System (pyttsx3)
	engine = pyttsx3.init()
	if rate is not None:
		try: engine.setProperty('rate', int(rate))
		except Exception: pass
	if volume is not None:
		try:
			vol = float(volume)
			if 0.0 <= vol <= 1.0:
				engine.setProperty('volume', vol)
		except Exception: pass
	voices = engine.getProperty('voices')
	if voice_idx is not None and 0 <= voice_idx < len(voices):
		try: engine.setProperty('voice', voices[voice_idx].id)
		except Exception: pass
	# write to temp wav
	with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tf:
		wav_path = tf.name
	engine.save_to_file(text, wav_path)
	engine.runAndWait()
	audio = AudioSegment.from_file(wav_path)
	if max_seconds and max_seconds > 0:
		cur_len = len(audio)/1000.0
		if cur_len > max_seconds and cur_len > 0.05:
			factor = cur_len / max_seconds
			try:
				audio = audio.speedup(playback_speed=factor)
			except Exception:
				pass
	out_path = os.path.join('sound-clips', f"{basename}.mp3")
	audio.export(out_path, format='mp3')
	try: os.remove(wav_path)
	except: pass
	return out_path

# ---- Voices listing (cached) ----
_voices_cache = {"data": None, "ts": 0}
def list_voices_cached():
	import time
	now = time.time()
	if _voices_cache["data"] and now - _voices_cache["ts"] < 300:
		return _voices_cache["data"]
	engine = pyttsx3.init()
	voices = engine.getProperty('voices')
	out = []
	for idx, v in enumerate(voices):
		langs = getattr(v, 'languages', [])
		out.append({"index": idx, "name": v.name, "id": v.id, "languages": [str(l) for l in langs]})
	_voices_cache["data"] = out
	_voices_cache["ts"] = now
	return out

@app.route('/api/sounds/voices')
async def api_list_voices():
	data = await asyncio.to_thread(list_voices_cached)
	return jsonify(data)

# ---- gTTS Languages (cached 24h) ----
_gtts_lang_cache = {"data": None, "ts": 0}
def list_gtts_languages_cached():
	import time
	from gtts.lang import tts_langs
	now = time.time()
	if _gtts_lang_cache['data'] and now - _gtts_lang_cache['ts'] < 86400:
		return _gtts_lang_cache['data']
	mapping = tts_langs()
	data = [{"code": code, "name": name} for code, name in sorted(mapping.items(), key=lambda kv: kv[0])]
	_gtts_lang_cache['data'] = data
	_gtts_lang_cache['ts'] = now
	return data

@app.route('/api/sounds/gtts_languages')
async def api_gtts_languages():
	data = await asyncio.to_thread(list_gtts_languages_cached)
	return jsonify(data)

@app.route('/api/sounds/generate/countdown', methods=['POST'])
async def api_generate_countdown():
	data = await request.get_json(force=True)
	try:
		start = int(data.get('start'))
		end = int(data.get('end'))
		language = data.get('language','en')
		base_name_raw = data.get('name') or f"countdown-{start}-{end}"
	except Exception:
		return jsonify({"error": "invalid parameters"}), 400
	if start < end:
		return jsonify({"error": "start must be >= end"}), 400
	# enforce client-supplied name max length before sanitization
	if not isinstance(base_name_raw, str) or len(base_name_raw) > 120:
		return jsonify({"error": "invalid name"}), 400
	basename = sanitize_basename(base_name_raw)
	# uniqueness
	out_rel = f"{basename}.mp3"
	out_abs = _abs_sound_path(out_rel)
	if not out_abs:
		return jsonify({"error": "invalid target path"}), 400
	if os.path.exists(out_abs):
		return jsonify({"error": "sound already exists"}), 400
	# generate in thread; ensure atomic write by writing to temp path then replace
	def _gen():
		tmp = out_abs + '.tmp'
		generate_countdown_sound(start, end, language, basename)
		# generate_countdown_sound currently writes directly; ensure rename if it created expected file
		produced = os.path.join('sound-clips', f"{basename}.mp3")
		if os.path.exists(produced):
			os.replace(produced, out_abs)
	await asyncio.to_thread(_gen)
	return jsonify({"ok": True, "name": basename})

@app.route('/api/sounds/generate/tts', methods=['POST'])
async def api_generate_tts():
	data = await request.get_json(force=True)
	text = (data or {}).get('text')
	if not text:
		return jsonify({"error": "text required"}), 400
	# basic rate limiting to avoid abuse of gTTS or system TTS
	client_ip = _client_ip()
	if not _rate_allow('tts_generate', client_ip, limit=6, window_seconds=60):
		return jsonify({"error": "rate limit exceeded"}), 429
	engine_choice = (data.get('engine') or 'system').lower()
	if engine_choice not in ('system','gtts'):
		engine_choice = 'system'
	voice_idx = data.get('voice_idx') if engine_choice == 'system' else None
	try:
		voice_idx = int(voice_idx) if voice_idx is not None else None
	except: voice_idx=None
	max_seconds = data.get('max_seconds') if engine_choice == 'system' else None
	try:
		max_seconds = float(max_seconds) if max_seconds is not None else None
	except: max_seconds=None
	rate = data.get('rate') if engine_choice == 'system' else None
	try: rate = int(rate) if rate is not None else None
	except: rate=None
	volume = data.get('volume') if engine_choice == 'system' else None
	try: volume = float(volume) if volume is not None else None
	except: volume=None
	gtts_lang = data.get('language') if engine_choice == 'gtts' else None
	base_name_raw = data.get('name') or text[:30].replace(' ','-')
	if not isinstance(base_name_raw, str) or len(base_name_raw) > 120:
		return jsonify({"error": "invalid name"}), 400
	basename = sanitize_basename(base_name_raw)
	out_rel = f"{basename}.mp3"
	out_abs = _abs_sound_path(out_rel)
	if not out_abs:
		return jsonify({"error": "invalid target path"}), 400
	if os.path.exists(out_abs):
		return jsonify({"error": "sound already exists"}), 400

	def _gen_t():
		# generate to temporary, then move
		tmp = out_abs + '.tmp'
		generate_tts_sound(text, voice_idx, max_seconds, basename, engine_choice, rate, volume, gtts_lang)
		produced = os.path.join('sound-clips', f"{basename}.mp3")
		if os.path.exists(produced):
			os.replace(produced, out_abs)
	await asyncio.to_thread(_gen_t)
	return jsonify({"ok": True, "name": basename, "engine": engine_choice})

@app.route('/api/sounds/<name>', methods=['DELETE'])
async def api_delete_sound(name):
	# Only allow deletion of sanitized basenames; reject raw paths
	if not isinstance(name, str) or len(name) > 200:
		return jsonify({"error": "invalid name"}), 400
	basename = sanitize_basename(name)
	out_rel = f"{basename}.mp3"
	out_abs = _abs_sound_path(out_rel)
	if not out_abs or not os.path.exists(out_abs):
		return jsonify({"error": "not found"}), 404
	try:
		os.remove(out_abs)
		return jsonify({"ok": True})
	except Exception as e:
		return jsonify({"error": str(e)}), 500

@app.route('/sound-clips/<fname>')
async def serve_sound(fname):
	# allow only .mp3 and sanitize base
	if not isinstance(fname, str) or not fname.endswith('.mp3'):
		return jsonify({"error": "invalid file"}), 400
	# Normalize and verify resolution under sound-clips
	abs_path = _abs_sound_path(fname)
	if not abs_path:
		return jsonify({"error": "forbidden"}), 403
	if not os.path.exists(abs_path):
		return jsonify({"error": "not found"}), 404
	return await send_file(abs_path, mimetype='audio/mpeg')

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
	guild_id = data.get("guildId")
	channel_id = data.get("channelId")
	sound = data.get("sound")

	if guild_id is None:
		return jsonify({"error": "guildId required"}), 400
	try:
		guild_id = int(guild_id)
	except Exception:
		return jsonify({"error": "invalid guildId"}), 400

	guild = discord.utils.get(bot.guilds, id=guild_id)
	if not guild:
		return jsonify({"error": "Guild not found"}), 404

	voice_client = guild.voice_client
	# If not connected, but channelId provided, try to join that channel
	if not voice_client and channel_id is not None:
		try:
			cid = int(channel_id)
		except Exception:
			cid = None
		if cid:
			ch = discord.utils.get(guild.channels, id=cid)
			if ch and isinstance(ch, discord.VoiceChannel):
				try:
					await ch.connect()
					voice_client = guild.voice_client
				except Exception as e:
					return jsonify({"error": f"Failed to connect to channel: {e}"}), 500

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

# ---------------- Rally Tracking Endpoints ----------------

@app.route('/api/rally/snapshot', methods=['GET'])
async def rally_snapshot():
	snap = await rally_store.snapshot()
	return jsonify(snap)

@app.route('/api/rally/changes', methods=['GET'])
async def rally_changes():
	try:
		since = request.args.get('since', type=int)
		if since is None:
			return jsonify({"error": "missing 'since' query param"}), 400
		timeout = request.args.get('timeout', type=int, default=25)
		if timeout < 1:
			timeout = 1
		if timeout > 60:
			timeout = 60
		seq, events = await rally_store.wait_for_events(since, timeout=timeout)
		return jsonify({"seq": seq, "events": events})
	except Exception as e:
		logger.exception("/api/rally/changes error")
		return jsonify({"error": str(e)}), 500

# Players CRUD
@app.route('/api/players', methods=['POST'])
async def create_player():
	data = await request.get_json(force=True)
	name = (data or {}).get('name')
	march_no_pets = (data or {}).get('march_time_no_pets_seconds')
	march_with_pets = (data or {}).get('march_time_with_pets_seconds')
	pet_status = (data or {}).get('pet_status', 'none')
	pet_activated_at = (data or {}).get('pet_activated_at', 0)
	if name is None:
		return jsonify({"error": "name required"}), 400
	# Allow missing march times (set to 0) or missing with_pets (reuse no_pets if provided)
	if march_no_pets is None:
		march_no_pets = 0
	if march_with_pets is None:
		march_with_pets = march_no_pets
	try:
		res = await rally_store.create_player(name, int(march_no_pets), int(march_with_pets), pet_status=pet_status, pet_activated_at=int(pet_activated_at or 0))
		return jsonify({"ok": True, **res})
	except DataValidationError as e:
		return jsonify({"error": str(e)}), 400
	except Exception as e:
		logger.exception("create_player error")
		return jsonify({"error": str(e)}), 500

@app.route('/api/players/<player_id>', methods=['PUT','PATCH'])
async def update_player(player_id):
	data = await request.get_json(force=True)
	try:
		ok = await rally_store.update_player(player_id, **(data or {}))
		if not ok:
			return jsonify({"error": "player not found"}), 404
		return jsonify({"ok": True})
	except Exception as e:
		logger.exception("update_player error")
		return jsonify({"error": str(e)}), 500

@app.route('/api/players/<player_id>', methods=['DELETE'])
async def delete_player(player_id):
	try:
		ok = await rally_store.delete_player(player_id)
		if not ok:
			return jsonify({"error": "player not found"}), 404
		return jsonify({"ok": True})
	except Exception as e:
		logger.exception("delete_player error")
		return jsonify({"error": str(e)}), 500

# Rallies CRUD
@app.route('/api/rallies', methods=['POST'])
async def create_rally():
	data = await request.get_json(force=True)
	owner_player_id = (data or {}).get('owner_player_id')
	created_ts = (data or {}).get('created_ts')
	if not owner_player_id:
		return jsonify({"error": "owner_player_id required"}), 400
	if created_ts is None:
		import time
		created_ts = int(time.time())
	try:
		res = await rally_store.create_rally(owner_player_id, int(created_ts))
		return jsonify({"ok": True, **res})
	except DataValidationError as e:
		return jsonify({"error": str(e)}), 400
	except Exception as e:
		logger.exception("create_rally error")
		return jsonify({"error": str(e)}), 500

@app.route('/api/rallies/<rally_id>/adjust', methods=['PATCH'])
async def adjust_rally(rally_id):
	data = await request.get_json(force=True)
	delta_seconds = (data or {}).get('delta_seconds')
	if delta_seconds is None:
		return jsonify({"error": "delta_seconds required"}), 400
	try:
		ok = await rally_store.adjust_rally_created(rally_id, int(delta_seconds))
		if not ok:
			return jsonify({"error": "rally not found"}), 404
		return jsonify({"ok": True})
	except Exception as e:
		logger.exception("adjust_rally error")
		return jsonify({"error": str(e)}), 500

@app.route('/api/rallies/<rally_id>', methods=['DELETE'])
async def delete_rally(rally_id):
	try:
		ok = await rally_store.delete_rally(rally_id)
		if not ok:
			return jsonify({"error": "rally not found"}), 404
		return jsonify({"ok": True})
	except Exception as e:
		logger.exception("delete_rally error")
		return jsonify({"error": str(e)}), 500

@app.route('/api/rally/pattern', methods=['GET'])
async def rally_pattern():
	try:
		exclude_landed = request.args.get('exclude_landed', 'false').lower() in ('1','true','yes','on')
		res = await rally_store.arrival_pattern(exclude_landed=exclude_landed)
		return jsonify(res)
	except Exception as e:
		logger.exception("rally_pattern error")
		return jsonify({"error": str(e)}), 500


async def main_web():
	# Start the Quart server in a background task, then confirm it's accepting connections.
	# Use an explicit shutdown event and pass its wait() as the shutdown_trigger
	# to Hypercorn so we control server shutdown (avoid conflicts with Hypercorn's
	# own signal handlers when the application installs its own handlers).
	global web_shutdown_event
	web_shutdown_event = asyncio.Event()
	server_task = asyncio.create_task(
		app.run_task(host=webserver_host, port=webserver_port, shutdown_trigger=web_shutdown_event.wait)
	)
	try:
		# No external pre-bind test here: rely on the in-process readiness signal
		# (using @app.before_serving -> web_ready) to determine success/failure.
		msg = f"Starting web server on {webserver_host}:{webserver_port}"
		try:
			log_message(msg, category="web")
		except Exception:
			logger.info(msg)

		# Wait for the in-process readiness signal (set by @app.before_serving).
		# This is deterministic and avoids probing the TCP socket externally.
		try:
			await asyncio.wait_for(web_ready.wait(), timeout=5.0)
		except Exception as e:
			# server didn't signal readiness in time; cancel and surface
			server_task.cancel()
			raise RuntimeError(f"web server failed to become ready on {webserver_host}:{webserver_port}: {e}")

		try:
			log_message(f"Web server signalled readiness on {webserver_host}:{webserver_port}", category="web")
		except Exception:
			logger.info(f"Web server signalled readiness on {webserver_host}:{webserver_port}")

		# server task running; await it indefinitely
		await server_task
	except asyncio.CancelledError:
		# Request Hypercorn to shutdown first so it can stop accepting new
		# connections and unblock any awaits inside the server.
		if not web_shutdown_event.is_set():
			web_shutdown_event.set()
		server_task.cancel()
		with contextlib.suppress(asyncio.CancelledError):
			await server_task
		raise
	except Exception:
		server_task.cancel()
		raise
