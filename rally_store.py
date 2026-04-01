#!/usr/bin/env python3
"""Rally tracking storage and event bus.

Responsibilities:
- Load & validate data.json (create if absent)
- Provide CRUD for players and rallies (rally has only created_ts; derive launch/landing externally)
- Manage pet status auto-expiration (2h window)
- Compute arrival pattern (landing offsets grouped)
- Event bus: sequence id incremented per mutation; retain recent events for diff delivery

Thread/async model: Called from Quart async handlers; internal operations kept simple & synchronous except
for long-poll waiters which will use asyncio.Event.
"""
from __future__ import annotations
import json, os, time, uuid, asyncio, logging
from typing import Dict, Any, List, Optional, Deque, Tuple
from collections import deque

logger = logging.getLogger(__name__)
DEFAULT_DATA_FILE = os.getenv("RALLY_DATA_FILE", "data.json")
EVENT_RETENTION = 500
PET_ACTIVE_SECONDS = 7200
RALLY_PREP_SECONDS = 300

class DataValidationError(Exception):
    pass

class RallyStore:
    def __init__(self, data_file: Optional[str] = None):
        self._lock = asyncio.Lock()
        self._data = {}
        self._seq = 0
        self._events = deque(maxlen=EVENT_RETENTION)
        self._waiters = []
        # write batching state
        self._dirty = False
        self._flush_in_progress = False
        self._flush_task = None
        self._data_file = data_file or DEFAULT_DATA_FILE
        self._load_or_init()

    # ---------------- Persistence ----------------
    def _load_or_init(self):
        if not os.path.exists(self._data_file):
            logger.info("data.json not found; creating new store")
            now = int(time.time())
            self._data = {"meta": {"version": 1, "created": now, "updated": now}, "players": {}, "rallies": {}}
            # during init we can do a direct sync write (event loop not yet running)
            self._atomic_write_sync()
        else:
            try:
                with open(self._data_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                self._validate_schema(self._data)
            except Exception as e:
                logger.error("Failed to load or validate data.json: %s", e)
                raise

    def _atomic_write_sync(self):
        tmp = self._data_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, separators=(",", ":"))
        os.replace(tmp, self._data_file)

    async def _atomic_write(self):
        # offload to thread to avoid blocking event loop for disk IO
        await asyncio.to_thread(self._atomic_write_sync)

    # --------------- Batched Persist (fire & forget) ---------------
    def _request_persist(self):
        """Mark data dirty and ensure a background flush task exists.

        Non-blocking: returns immediately. Multiple calls coalesce.
        """
        # Mark dirty under lock context (caller already holds lock in our usage), but be defensive.
        if not self._dirty:
            self._dirty = True
        if not self._flush_task or self._flush_task.done():
            # schedule new flush
            loop = asyncio.get_event_loop()
            self._flush_task = loop.create_task(self._flush_loop())

    async def _flush_loop(self):
        # Single task that keeps flushing while dirty toggles get set.
        # To limit rapid re-writes, we introduce a tiny debounce (10ms) to batch bursts.
        try:
            while True:
                await asyncio.sleep(0.01)  # debounce window
                async with self._lock:
                    if not self._dirty:
                        break
                    self._dirty = False
                    # snapshot current data to serialize outside lock for minimal lock hold
                    data_snapshot = json.dumps(self._data, separators=(",", ":"))
                # perform blocking IO off-thread
                await asyncio.to_thread(self._write_json_string, data_snapshot)
        except Exception as e:
            logger.error("Flush loop error: %s", e)

    def _write_json_string(self, data: str):
        tmp = self._data_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, self._data_file)

    async def force_flush(self):
        """Force immediate persistence if dirty (used in tests)."""
        async with self._lock:
            if not self._dirty:
                return
            data_snapshot = json.dumps(self._data, separators=(",", ":"))
            self._dirty = False
        await asyncio.to_thread(self._write_json_string, data_snapshot)

    def _touch(self):
        self._data["meta"]["updated"] = int(time.time())

    # ---------------- Schema Validation ----------------
    def _validate_schema(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            raise DataValidationError("Root must be object")
        for key in ("meta", "players", "rallies"):
            if key not in data:
                raise DataValidationError(f"Missing top-level key: {key}")
        # minimal further checks; expand later

    # ---------------- Helpers ----------------
    def _new_player_id(self) -> str:
        return str(uuid.uuid4())

    def _new_rally_id(self) -> str:
        return str(uuid.uuid4())

    def _effective_march_time(self, player: Dict[str, Any], now: Optional[int] = None) -> int:
        now = now or int(time.time())
        status = player.get("pet_status")
        if status == 'active':
            activated = player.get("pet_activated_at", 0)
            if activated and now < activated + PET_ACTIVE_SECONDS:
                return int(player.get("march_time_with_pets_seconds", player.get("march_time_no_pets_seconds", 0)))
            else:
                # auto-expire
                player["pet_status"] = 'expired'
                return int(player.get("march_time_no_pets_seconds", 0))
        return int(player.get("march_time_no_pets_seconds", 0))

    def _landing_ts(self, rally: Dict[str, Any], player: Dict[str, Any], now: Optional[int] = None) -> int:
        created_ts = rally["created_ts"]
        return created_ts + RALLY_PREP_SECONDS + self._effective_march_time(player, now)

    def _append_event(self, evt: Dict[str, Any]):
        self._seq += 1
        evt["seq"] = self._seq
        self._events.append(evt)
        # wake waiters
        for fut in list(self._waiters):
            if not fut.done():
                fut.set_result(True)
        self._waiters.clear()

    # ---------------- Public API ----------------
    async def snapshot(self) -> Dict[str, Any]:
        async with self._lock:
            # ensure pet auto-expiry update reflected
            now = int(time.time())
            for p in self._data["players"].values():
                self._effective_march_time(p, now)  # updates status if needed
            snap = {
                "seq": self._seq,
                "players": self._data["players"],
                "rallies": self._data["rallies"],
            }
            return snap

    async def list_events_since(self, since: int) -> Tuple[int, List[Dict[str, Any]]]:
        async with self._lock:
            if since < self._seq - EVENT_RETENTION:
                # client too far behind
                return self._seq, [{"type": "full_reset"}]
            events = [e for e in self._events if e["seq"] > since]
            return self._seq, events

    async def wait_for_events(self, since: int, timeout: int) -> Tuple[int, List[Dict[str, Any]]]:
        # quick check without holding waiter list
        async with self._lock:
            if since < self._seq:
                # gather directly
                events = [e for e in self._events if e["seq"] > since] if since >= self._seq - EVENT_RETENTION else [{"type": "full_reset"}]
                return self._seq, events
            # need to wait
            fut = asyncio.get_event_loop().create_future()
            self._waiters.append(fut)
        try:
            await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            # timeout: just fall through
            pass
        async with self._lock:
            events = [e for e in self._events if e["seq"] > since] if since >= self._seq - EVENT_RETENTION else [{"type": "full_reset"}]
            return self._seq, events

    async def create_player(self, name: str, march_no_pets: int | None, march_with_pets: int | None, pet_status: str = 'none', pet_activated_at: int = 0) -> Dict[str, Any]:
        async with self._lock:
            pid = self._new_player_id()
            self._data["players"][pid] = {
                "name": name,
                "march_time_no_pets_seconds": int(march_no_pets) if march_no_pets is not None else 0,
                # if with_pets missing, fallback to no-pets value
                "march_time_with_pets_seconds": int(march_with_pets) if march_with_pets is not None else int(march_no_pets) if march_no_pets is not None else 0,
                "pet_status": pet_status,
                "pet_activated_at": int(pet_activated_at) if pet_activated_at else 0,
            }
            self._touch()
            self._request_persist()
            self._append_event({"type": "player.create", "player_id": pid})
            return {"player_id": pid}

    async def update_player(self, player_id: str, **fields) -> bool:
        async with self._lock:
            player = self._data["players"].get(player_id)
            if not player:
                return False
            allowed = {"name", "march_time_no_pets_seconds", "march_time_with_pets_seconds", "pet_status", "pet_activated_at"}
            for k, v in fields.items():
                if k in allowed and v is not None:
                    player[k] = v
            self._touch(); self._request_persist()
            self._append_event({"type": "player.update", "player_id": player_id, "fields": list(fields.keys())})
            return True

    async def delete_player(self, player_id: str) -> bool:
        async with self._lock:
            if player_id not in self._data["players"]:
                return False
            # remove associated rallies
            to_delete = [rid for rid, r in self._data["rallies"].items() if r["owner_player_id"] == player_id]
            for rid in to_delete:
                del self._data["rallies"][rid]
                self._append_event({"type": "rally.delete", "rally_id": rid})
            del self._data["players"][player_id]
            self._touch(); self._request_persist()
            self._append_event({"type": "player.delete", "player_id": player_id})
            return True

    async def create_rally(self, owner_player_id: str, created_ts: int) -> Dict[str, Any]:
        async with self._lock:
            if owner_player_id not in self._data["players"]:
                raise DataValidationError("owner_player_id not found")
            now = int(time.time())
            # Validate created_ts within last 5 min (late entry) and not future beyond small skew
            if created_ts > now + 2:
                raise DataValidationError("created_ts cannot be in the far future")
            if created_ts < now - RALLY_PREP_SECONDS:
                raise DataValidationError("created_ts older than prep window (300s)")
            rid = self._new_rally_id()
            self._data["rallies"][rid] = {
                "owner_player_id": owner_player_id,
                "created_ts": int(created_ts)
            }
            self._touch(); self._request_persist()
            self._append_event({"type": "rally.create", "rally_id": rid, "player_id": owner_player_id})
            return {"rally_id": rid}

    async def adjust_rally_created(self, rally_id: str, delta_seconds: int) -> bool:
        async with self._lock:
            rally = self._data["rallies"].get(rally_id)
            if not rally:
                return False
            rally["created_ts"] += delta_seconds
            now = int(time.time())
            # Keep within valid window
            if rally["created_ts"] < now - RALLY_PREP_SECONDS:
                rally["created_ts"] = now - RALLY_PREP_SECONDS
            if rally["created_ts"] > now:
                rally["created_ts"] = now
            self._touch(); self._request_persist()
            self._append_event({"type": "rally.update", "rally_id": rally_id, "fields": ["created_ts"]})
            return True

    async def delete_rally(self, rally_id: str) -> bool:
        async with self._lock:
            if rally_id not in self._data["rallies"]:
                return False
            del self._data["rallies"][rally_id]
            self._touch(); self._request_persist()
            self._append_event({"type": "rally.delete", "rally_id": rally_id})
            return True

    async def arrival_pattern(self, exclude_landed: bool = False) -> Dict[str, Any]:
        async with self._lock:
            now = int(time.time())
            # Build list of (rally_id, landing_ts)
            landing: List[Tuple[str, int]] = []
            for rid, r in self._data["rallies"].items():
                player = self._data["players"].get(r["owner_player_id"])
                if not player:
                    continue
                land_ts = self._landing_ts(r, player, now)
                if exclude_landed and land_ts < now:
                    continue
                landing.append((rid, land_ts))
            if not landing:
                return {"seq": self._seq, "pattern": [], "entries": []}
            # sort by landing_ts
            landing.sort(key=lambda x: x[1])
            first = landing[0][1]
            entries = []
            pattern = []
            for rid, ts in landing:
                offset = ts - first
                offset_s = offset // 1  # integer seconds
                pattern.append(int(offset_s))
                entries.append({
                    "rally_id": rid,
                    "landing_ts": ts,
                    "offset_seconds": int(offset_s)
                })
            return {"seq": self._seq, "pattern": pattern, "entries": entries}

# Singleton instance for application use
rally_store = RallyStore()
