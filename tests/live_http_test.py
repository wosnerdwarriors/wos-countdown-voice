#!/usr/bin/env python3
"""Live HTTP integration test against a running server.

Usage:
  python tests/live_http_test.py                # assumes http://127.0.0.1:5544
  python tests/live_http_test.py --host 0.0.0.0 --port 8080
  python tests/live_http_test.py --base-url http://myhost:9999

Exit code non‑zero on failure. Prints a concise summary.
"""
from __future__ import annotations
import argparse, sys, time, json, random, string
from typing import Dict, Any, List
import urllib.request, urllib.error, urllib.parse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5544

class HttpClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        self.base = base_url
        self.timeout = timeout

    def _request(self, method: str, path: str, data: Dict[str, Any] | None = None) -> Dict[str, Any]:
        url = self.base + path
        headers = {"Content-Type": "application/json"}
        body = None
        if data is not None:
            body = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                if not raw:
                    return {"_empty": True}
                return json.loads(raw.decode('utf-8'))
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode('utf-8')
            except Exception:
                detail = ''
            raise RuntimeError(f"HTTP {e.code} {method} {path}: {detail}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Connection error {method} {path}: {e}")

    def get(self, path: str):
        return self._request('GET', path)

    def post(self, path: str, data: Dict[str, Any]):
        return self._request('POST', path, data)

    def patch(self, path: str, data: Dict[str, Any]):
        return self._request('PATCH', path, data)

    def delete(self, path: str):
        return self._request('DELETE', path)

# ---------------- Tests ----------------

def rand_name(prefix: str = 'T') -> str:
    return prefix + ''.join(random.choice(string.ascii_lowercase) for _ in range(6))

class LiveSuite:
    def __init__(self, client: HttpClient):
        self.c = client
        self.failures: List[str] = []
        self.created_player_ids: List[str] = []
        self.created_rally_ids: List[str] = []

    def check(self, condition: bool, msg: str):
        if not condition:
            self.failures.append(msg)
            print(f"[FAIL] {msg}")
        else:
            print(f"[OK]   {msg}")

    def run(self):
        start = time.time()
        self.test_snapshot()
        self.test_player_crud()
        self.test_rally_flow()
        self.test_long_poll()
        self.test_audio_config()
        elapsed = time.time() - start
        print(f"--- Completed in {elapsed:.2f}s ---")
        if self.failures:
            print(f"{len(self.failures)} failing checks")
            for f in self.failures:
                print(f" - {f}")
            return 1
        print("All checks passed")
        return 0

    def test_snapshot(self):
        data = self.c.get('/api/rally/snapshot')
        self.check('seq' in data, 'snapshot has seq')
        self.check('players' in data and isinstance(data['players'], dict), 'snapshot players dict')

    def test_player_crud(self):
        name = rand_name('P')
        res = self.c.post('/api/players', {
            'name': name,
            'march_time_no_pets_seconds': 120,
            'march_time_with_pets_seconds': 100,
            'pet_status': 'none'
        })
        pid = res.get('player_id')
        self.check(bool(pid), 'player create returned id')
        if pid:
            self.created_player_ids.append(pid)
            upd = self.c.patch(f'/api/players/{pid}', {'name': name+'x'})
            self.check(upd.get('ok') is True, 'player update ok')

    def test_rally_flow(self):
        # ensure at least one player
        if not self.created_player_ids:
            self.test_player_crud()
        pid = self.created_player_ids[0]
        create = self.c.post('/api/rallies', {'owner_player_id': pid})
        rid = create.get('rally_id')
        self.check(bool(rid), 'rally create returned id')
        if rid:
            self.created_rally_ids.append(rid)
            adj = self.c.patch(f'/api/rallies/{rid}/adjust', {'delta_seconds': -5})
            self.check(adj.get('ok') is True, 'rally adjust ok')
            pat = self.c.get('/api/rally/pattern')
            self.check('pattern' in pat, 'pattern endpoint returns pattern')

    def test_long_poll(self):
        # get current seq
        snap = self.c.get('/api/rally/snapshot')
        seq = snap.get('seq', 0)
        # trigger change in another request cycle
        if not self.created_player_ids:
            self.test_player_crud()
        pid = self.created_player_ids[0]
        # create rally to generate event
        self.c.post('/api/rallies', {'owner_player_id': pid})
        # long poll with since old seq (should return immediately)
        changes = self.c.get(f'/api/rally/changes?since={seq}&timeout=5')
        self.check('events' in changes, 'changes returns events list')
        ev = changes.get('events', [])
        self.check(any(e.get('type') == 'rally.create' for e in ev), 'rally.create event present')

    def test_audio_config(self):
        # initial state
        st = self.c.get('/api/rally/audio')
        self.check('enabled' in st, 'audio state returns enabled field')
        # update config
        upd = self.c.post('/api/rally/audio/config', {
            'enabled': True,
            'sound_name': st.get('sound_name',''),
            'lead_seconds': 15,
            'offset_ms': 25,
            'guild_id': st.get('guild_id'),
            'channel_id': st.get('channel_id'),
        })
        self.check(upd.get('ok') is True, 'audio config update ok')
        st2 = self.c.get('/api/rally/audio')
        self.check(st2.get('lead_seconds') == 15, 'audio lead_seconds persisted')
        # adjust offset
        adj = self.c.post('/api/rally/audio/adjust', {'delta_ms': 5})
        self.check(adj.get('ok') is True, 'audio adjust offset ok')
        st3 = self.c.get('/api/rally/audio')
        self.check(st3.get('offset_ms') == 30, 'audio offset_ms adjusted (25+5)')
        # stop attempt (may fail if no guild configured; treat presence of ok key as success)
        try:
            stop_res = self.c.post('/api/rally/audio/stop', {})
            self.check('ok' in stop_res, 'audio stop endpoint reachable')
        except Exception as e:
            self.check(False, f'audio stop endpoint error: {e}')


def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Live HTTP integration tests for rally APIs.')
    p.add_argument('--host', default=None, help='Host (default 127.0.0.1)')
    p.add_argument('--port', type=int, default=None, help='Port (default 5544)')
    p.add_argument('--base-url', default=None, help='Override full base URL (ex: http://server:5544)')
    p.add_argument('--timeout', type=float, default=10.0, help='Per-request timeout seconds')
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.base_url:
        base = args.base_url
    else:
        host = args.host or DEFAULT_HOST
        port = args.port or DEFAULT_PORT
        base = f'http://{host}:{port}'
    print(f'Base URL: {base}')
    client = HttpClient(base, timeout=args.timeout)
    suite = LiveSuite(client)
    rc = suite.run()
    sys.exit(rc)

if __name__ == '__main__':
    main()
