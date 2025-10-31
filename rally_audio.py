import asyncio, json, os, time, logging
from typing import Optional, Dict, Any
from discord_bot import bot, play_sound, log_message
from rally_store import rally_store
import discord

logger = logging.getLogger(__name__)

AUDIO_CONFIG_FILE = os.getenv("RALLY_AUDIO_CONFIG_FILE", "rally_audio_config.json")
DEFAULTS = {
    "enabled": False,
    "sound_name": "",
    "lead_seconds": 0,  # how many seconds BEFORE earliest landing to start playback (sound should contain countdown)
    "offset_ms": 0,     # fine adjustment (+ delays playback, - earlier)
    "guild_id": None,
    "channel_id": None,
    "last_play_landing_ts": 0,
    # tracking behavior
    "track_mode": "earliest",  # earliest | single
    "track_rally_id": None,
    # optional prefix playback
    "prefix_sound_name": "",
    "prefix_advance_seconds": 0,  # seconds BEFORE main scheduled fire to play prefix
    "last_prefix_landing_ts": 0,
}

class AudioScheduler:
    def __init__(self):
        self._cfg: Dict[str, Any] = dict(DEFAULTS)
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._watcher_task: Optional[asyncio.Task] = None
        self._next_schedule_landing_ts: int = 0
        self._next_fire_at_monotonic: float = 0.0
        # kind of next fire: 'prefix', 'main', or ''
        self._next_fire_kind: str = ''
        self._wake_event = asyncio.Event()
        # throttling helpers
        self._last_connect_error_log: float = 0.0
        self._load()

    # ------------- Persistence -------------
    def _load(self):
        if os.path.exists(AUDIO_CONFIG_FILE):
            try:
                with open(AUDIO_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._cfg.update({k: data.get(k, v) for k, v in DEFAULTS.items()})
            except Exception as e:
                logger.error("Failed loading audio config: %s", e)
        else:
            self._persist_sync()

    def _persist_sync(self):
        tmp = AUDIO_CONFIG_FILE + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self._cfg, f, separators=(",", ":"))
        os.replace(tmp, AUDIO_CONFIG_FILE)

    async def _persist(self):
        await asyncio.to_thread(self._persist_sync)

    # ------------- Public API -------------
    async def get_state(self) -> Dict[str, Any]:
        async with self._lock:
            state = dict(self._cfg)
            # augment with derived scheduling info
            state["next_landing_ts"] = self._next_schedule_landing_ts
            if self._next_fire_at_monotonic:
                # convert monotonic -> wall clock approximation
                delta = self._next_fire_at_monotonic - time.monotonic()
                if delta < 0: delta = 0
                state["scheduled_fire_unix"] = int(time.time() + delta)
            else:
                state["scheduled_fire_unix"] = 0
            state["next_fire_kind"] = self._next_fire_kind
            state["connected"] = self._connected_unlocked()
            return state

    async def update_config(self, **fields):
        async with self._lock:
            for k, v in fields.items():
                if k in self._cfg:
                    self._cfg[k] = v
            await self._persist()
            self._wake_event.set()
        log_message(f"Audio config updated: {fields}", category="audio_config")

    async def adjust_offset_ms(self, delta_ms: int):
        async with self._lock:
            self._cfg['offset_ms'] = int(self._cfg.get('offset_ms', 0)) + int(delta_ms)
            await self._persist()
            self._wake_event.set()
        log_message(f"Audio offset_ms adjusted by {delta_ms}", category="audio_config")

    def _connected_unlocked(self) -> bool:
        gid = self._cfg.get('guild_id')
        if not gid: return False
        try:
            gid_int = int(gid)
        except Exception:
            return False
        guild = discord.utils.get(bot.guilds, id=gid_int)
        if not guild: return False
        vc = guild.voice_client
        return vc is not None

    async def ensure_connected(self):
        async with self._lock:
            gid = self._cfg.get('guild_id')
            cid = self._cfg.get('channel_id')
        if not gid or not cid:
            return False
        try:
            gid_int = int(gid); cid_int = int(cid)
        except Exception:
            return False
        guild = discord.utils.get(bot.guilds, id=gid_int)
        if not guild:
            return False
        ch = discord.utils.get(guild.channels, id=cid_int)
        if not ch or not isinstance(ch, discord.VoiceChannel):
            return False
        if guild.voice_client and guild.voice_client.channel.id == ch.id:
            return True
        try:
            await ch.connect()
            return True
        except Exception as e:
            logger.error("Failed connect voice: %s", e)
            return False

    # ------------- Scheduling Loop -------------
    async def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())
        # start event watcher and keep reference so we can cancel on stop
        self._watcher_task = asyncio.create_task(self._rally_event_watcher())

    async def stop(self):
        """Cancel the scheduler and watcher tasks and persist state."""
        tasks = []
        if self._watcher_task and not self._watcher_task.done():
            self._watcher_task.cancel()
            tasks.append(self._watcher_task)
        if self._task and not self._task.done():
            self._task.cancel()
            tasks.append(self._task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        # persist current config to disk
        try:
            await self._persist()
        except Exception:
            logger.exception('Failed to persist audio scheduler state on stop')

    async def _rally_event_watcher(self):
        """Poll rally_store events sequence to auto-reschedule on any rally/player change."""
        seq = 0
        while True:
            try:
                # quick check snapshot seq; cheaper than long-poll for now
                snap = await rally_store.snapshot()
                cur = snap.get('seq', 0)
                if cur != seq:
                    seq = cur
                    # wake scheduler to recompute
                    self._wake_event.set()
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.error("rally_event_watcher error: %s", e)
                await asyncio.sleep(2.0)

    async def _run(self):
        log_message("Audio scheduler loop started", category="audio_scheduler")
        # Internal control exception used to signal a wake/recompute without
        # conflating with asyncio.CancelledError which indicates real shutdown.
        class _RecomputeNow(Exception):
            pass
        while True:
            try:
                await self._recompute_schedule()
                # compute sleep
                async with self._lock:
                    fire_monotonic = self._next_fire_at_monotonic
                if fire_monotonic <= 0:
                    # nothing to do; wait until config/event change
                    self._wake_event.clear()
                    await self._wake_event.wait()
                    continue
                # sleep until either time or wake_event
                while True:
                    remaining = fire_monotonic - time.monotonic()
                    if remaining <= 0:
                        break
                    # wait shorter of remaining or 1s or until wake
                    to_wait = min(1.0, remaining)
                    try:
                        await asyncio.wait_for(self._wake_event.wait(), timeout=to_wait)
                        # woke early; recompute schedule — use local exception so
                        # we don't accidentally swallow asyncio.CancelledError.
                        self._wake_event.clear()
                        raise _RecomputeNow()
                    except asyncio.TimeoutError:
                        pass
                # time reached; perform playback
                await self._fire_if_due()
            except _RecomputeNow:
                # normal internal control flow to recompute schedule
                continue
            except asyncio.CancelledError:
                # Real cancellation — stop the loop quietly and allow cleanup by caller
                logger.debug("Audio scheduler received CancelledError; exiting loop")
                break
            except Exception as e:
                logger.error("Audio scheduler loop error: %s", e)
                await asyncio.sleep(1)

    async def _recompute_schedule(self):
        async with self._lock:
            if not self._cfg.get('enabled'):
                self._next_schedule_landing_ts = 0
                self._next_fire_at_monotonic = 0
                self._next_fire_kind = ''
                return
        # get earliest landing
        tracked_landing_ts = 0
        pattern = await rally_store.arrival_pattern(exclude_landed=True)
        mode = self._cfg.get('track_mode','earliest')
        if mode == 'single' and self._cfg.get('track_rally_id'):
            rid = self._cfg.get('track_rally_id')
            # locate that rally landing
            for e in pattern.get('entries', []):
                if e['rally_id'] == rid:
                    tracked_landing_ts = e['landing_ts']
                    break
        if not tracked_landing_ts:
            # fallback earliest
            if pattern.get('entries'):
                tracked_landing_ts = min(e['landing_ts'] for e in pattern['entries'])
        async with self._lock:
            if not tracked_landing_ts:
                self._next_schedule_landing_ts = 0
                self._next_fire_at_monotonic = 0
                self._next_fire_kind = ''
                return
            # avoid duplicate for same landing
            if tracked_landing_ts == self._cfg.get('last_play_landing_ts'):
                self._next_schedule_landing_ts = 0
                self._next_fire_at_monotonic = 0
                self._next_fire_kind = ''
                return
            lead_seconds = int(self._cfg.get('lead_seconds', 0))
            offset_ms = int(self._cfg.get('offset_ms', 0))
            fire_at = tracked_landing_ts - lead_seconds + (offset_ms / 1000.0)
            now = time.time()
            # prefix logic
            prefix_sound = self._cfg.get('prefix_sound_name') or ''
            prefix_adv = int(self._cfg.get('prefix_advance_seconds') or 0)
            last_prefix_done = self._cfg.get('last_prefix_landing_ts')
            schedule_kind = 'main'
            fire_at_to_use = fire_at
            if prefix_sound and prefix_adv > 0 and last_prefix_done != tracked_landing_ts:
                prefix_fire_at = fire_at - prefix_adv
                if prefix_fire_at > now:
                    fire_at_to_use = prefix_fire_at
                    schedule_kind = 'prefix'
            if fire_at_to_use <= now:
                self._next_fire_at_monotonic = time.monotonic()
            else:
                delta = fire_at_to_use - now
                if delta < 0: delta = 0
                self._next_fire_at_monotonic = time.monotonic() + delta
            self._next_fire_kind = schedule_kind if self._next_fire_at_monotonic else ''
            self._next_schedule_landing_ts = tracked_landing_ts
    # Public test helper
    async def recompute_now_for_test(self):
        await self._recompute_schedule()

    async def _fire_if_due(self):
        async with self._lock:
            if not self._cfg.get('enabled'):
                return
            landing_ts = self._next_schedule_landing_ts
            if not landing_ts:
                return
            # ensure still earliest and not duplicate
            if landing_ts == self._cfg.get('last_play_landing_ts'):
                return
            sound = self._cfg.get('sound_name')
            guild_id = self._cfg.get('guild_id')
            if not sound or not guild_id:
                # prerequisites missing: unschedule to avoid busy loop
                self._next_schedule_landing_ts = 0
                self._next_fire_at_monotonic = 0
                self._next_fire_kind = ''
                return
            prefix_sound = self._cfg.get('prefix_sound_name') or ""
            prefix_adv = int(self._cfg.get('prefix_advance_seconds') or 0)
            last_prefix_done = self._cfg.get('last_prefix_landing_ts')
            fire_kind = self._next_fire_kind
        # verify earliest still valid and enough lead? tolerance few seconds
        pattern = await rally_store.arrival_pattern(exclude_landed=True)
        # Validate landing still relevant based on tracking mode
        mode = self._cfg.get('track_mode','earliest')
        valid = False
        if mode == 'earliest':
            # landing_ts must still be smallest
            if pattern.get('entries'):
                cur_min = min(e['landing_ts'] for e in pattern['entries'])
                if cur_min == landing_ts:
                    valid = True
        else:  # single
            rid = self._cfg.get('track_rally_id')
            for e in pattern.get('entries', []):
                if e['landing_ts'] == landing_ts and e['rally_id'] == rid:
                    valid = True; break
        if not valid:
            log_message("Scheduled landing no longer target; skipping", category="audio_scheduler")
            return
        # Branch: prefix vs main
        if fire_kind == 'prefix':
            ok = await self.ensure_connected()
            if not ok:
                log_message("Prefix: could not connect to voice channel", severity="error", category="audio_scheduler")
                # abort this attempt; will recompute schedule soon
                async with self._lock:
                    self._next_fire_at_monotonic = 0
                    self._next_fire_kind = ''
                return
            guild_pref = discord.utils.get(bot.guilds, id=int(guild_id))
            if guild_pref and prefix_sound:
                log_message(f"Playing prefix for landing {landing_ts}", category="audio_scheduler")
                await play_sound(prefix_sound, guild_pref)
                async with self._lock:
                    self._cfg['last_prefix_landing_ts'] = landing_ts
                    # schedule main fire
                    lead_seconds = int(self._cfg.get('lead_seconds', 0))
                    offset_ms = int(self._cfg.get('offset_ms', 0))
                    main_fire_at = landing_ts - lead_seconds + (offset_ms/1000.0)
                    now2 = time.time()
                    if main_fire_at <= now2:
                        self._next_fire_at_monotonic = time.monotonic()
                    else:
                        self._next_fire_at_monotonic = time.monotonic() + (main_fire_at - now2)
                    self._next_fire_kind = 'main'
                    await self._persist()
                self._wake_event.set()
            return
        # connect if needed
        ok = await self.ensure_connected()
        if not ok:
            # backoff + throttle logging
            nowm = time.monotonic()
            async with self._lock:
                # retry after 2s to avoid spin
                self._next_fire_at_monotonic = nowm + 2.0
            if nowm - self._last_connect_error_log > 5.0:
                log_message("Audio scheduler could not connect to voice channel", severity="error", category="audio_scheduler")
                self._last_connect_error_log = nowm
            return
        # play
        guild = discord.utils.get(bot.guilds, id=int(guild_id))
        if guild:
            await play_sound(sound, guild)
            async with self._lock:
                self._cfg['last_play_landing_ts'] = landing_ts
                await self._persist()
            log_message(f"Scheduled main audio played for landing {landing_ts}", category="audio_scheduler")
        # set schedule to none so recompute
        async with self._lock:
            self._next_schedule_landing_ts = 0
            self._next_fire_at_monotonic = 0
            self._next_fire_kind = ''
        self._wake_event.set()

    async def trigger_now(self):
        async with self._lock:
            if not self._cfg.get('enabled'):
                # allow manual trigger even if disabled? Keep simple: require enabled
                pass
            sound = self._cfg.get('sound_name')
            guild_id = self._cfg.get('guild_id')
        if not sound or not guild_id:
            return False
        ok = await self.ensure_connected()
        if not ok:
            return False
        guild = discord.utils.get(bot.guilds, id=int(guild_id))
        if not guild:
            return False
        await play_sound(sound, guild)
        return True


audio_scheduler = AudioScheduler()
