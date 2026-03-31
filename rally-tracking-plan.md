I have another rally tracker project that i want to implement into this and wire it into the website. This project has 2 forms. a website and a spreadsheet. I  will give you references to the source code of the website but some of the functionality doesn't exist there and is only in the spreadsheet which i can't give you but i can explain how it'll work. so i'll explain it like it's all one tool and you'll find PART of the logic in the website but not all of it

The way it works is like this

You have a list where you can add players
you add
player name, march time, pet status (no pets, pets active, pets expired)


We'll have multiple of the reason that we track pets is when pets are on, their march time decreases (i'll mention more about how much later or somewhere else),
also, when we notice their pets have been activated we can mark them as active and know that they'll expire in 2 hours (pets always last 2 hours)



The situation we're tracking is this

multiple players create a rally. A rally takes 5 minutes before it starts marching/moving. So when a player starts a rally, it's 5 minutes + march time until it lands on the target

We want to track multiple players and their marches in one section

then in another section we want to track when a rally is started/created. 
in the existing tool, it will show you the list of rallies and when they're landing and when they're launching in seconds live (we need both)

what we also want is the combination that would tell us the pattern of the landing

so let's say there's 5 rallies.
2 are landing at the same second, then 2 more are landing 1 second later and then 2 more are landing 2 seconds after that, then we want to see the pattern
0,0,1,1,2,2

We need to send our marches to refill off this pattern.

We'll build a visual tool but eventually build in automation to start a countdown bot but the way we normally use this countdown tool with our rally tracking tool is that we count up all these rallies and the pattern and we do an x second countdown before the rally lands. generally 80 seconds.

so the visual will write out
When the rally person	Chamy(30s)	rally countdown reaches 	40	Time left on their rally to march, you will hit the 	70	sound clip button

Sorted arrival offsets at castle from first to land:	0, 0, 1

etc etc



our rally tracker project allows us to set rallies in 2 ways
Exact sets with specific times
like player 1 has a rally running and it's going to launch in 4 minutes 30 seonds
plus it has + and - buttons to adjust the time live. this is what we have on the website currently

the other way we'd like to add is when we add a rally we say
player 2 is doing a rally and it is x seconds sooner/later than player 1

base a bit of the website we'd like based on the rallytracker project that i've copied the source into our project folder (just for reference so vscode can pick up the code)


Initially we just want to replicate the rally tracker as described visually but have it done in way that prepares it to be wired up where we can set the countdown bot to automatically start a countdown at a certain time and perhaps even call out a prefix of the arrival time pattern etc etc but let's just pull in the logic for the rally tracking


I want the tracking system tracked server side and saving the players and march times and pet starts (use a specific unixtime for the start time so if we reload, we know when it'll end)
Save in a new file called data.json and create the file if it doesn't exist. if we're starting try read the file and if it doesn't exist, create it. if it's corrupt or doesn't match the style of what we expect. Error out (for now)

---
## Development Plan (next steps to implement)

Purpose (revised): implement a self-contained server-side rally tracking backend integrated directly into the existing Quart web server (do NOT reuse or depend on the `rallytracker/` folder—it's temporary reference only). We'll replicate required front-end functionality with new templates and JS.

Scope now: persistent `data.json` storage, APIs for CRUD operations on players and rallies (a rally always belongs to a player), server-side arrival pattern computation, and UI to manage both entities.

High-level checklist
1. Define data model and file format for `data.json`.
2. Implement a small server module (`rally_store.py`) with read/write/validate logic and an in-memory cache.
3. Add REST endpoints in `web_server.py` to list/add/edit/delete players and rallies and to compute arrival patterns.
4. Wire `rallytracker/index.html` + JS to call the new endpoints.
5. Add server-side logic to compute combined arrival offsets and grouping pattern (like `0,0,1,1,2,2`).
6. Add UI for setting "relative to another player's rally" entries.
7. Add options to export/import `data.json` for backup.
8. Add unit tests for `rally_store.py` and the pattern computation.

Data model proposal (JSON) (revised: storage uses ONLY absolute timestamps; any relative input is resolved before persistence)
```
{
	"meta": {
		"version": 1,
		"created": 1694610000,
		"updated": 1694610000
	},
	"players": {
		"player-uuid-1": {
			"name": "Chamy",
			"march_time_no_pets_seconds": 30,   // base march time without pets
			"march_time_with_pets_seconds": 24, // effective march time when pets active (example)
			"pet_status": "none"|"active"|"expired",
			"pet_activated_at": 0              // unix epoch seconds if active (used to auto-expire at +7200)
		}
	},
			"rallies": {
				"rally-uuid-1": {
					"owner_player_id": "player-uuid-1",
					"created_ts": 1694610005            // absolute unix epoch seconds when rally was first started (start of fixed 300 s prep window)
				}
			}
}
```

UI relative-offset handling (clarified)
- The UI may let a user create a rally "+/- X seconds relative to rally Y" or "launch in HH:MM:SS".
- The client (or server endpoint logic) will translate that into a concrete absolute `launch_ts` before writing to storage. No `relative_to` or `relative_offset_seconds` keys are stored.

Rationale for dual march time fields
- Avoid recomputing dynamic pet-adjusted times; keeps logic explicit and auditable.
- Pet expiration logic: if `pet_status == active` AND `now >= pet_activated_at + 7200`, flip to `expired` automatically on read-modify or via a maintenance tick.

Backend logic to choose effective march time
```
if player.pet_status == 'active' and now < pet_activated_at + 7200:
		effective = march_time_with_pets_seconds
else:
		effective = march_time_no_pets_seconds
```
This keeps formulas transparent and removes hidden percentage modifiers.


Notes on march_time, rally timing, and pet handling (updated)
- A rally always has a fixed prep window of 5 minutes (300 seconds) from its true creation time.
- We store only `created_ts` (the moment the rally was actually started). Launch (march start) time is always `created_ts + 300`.
- Landing time = `created_ts + 300 + effective_march_time`.
- Late entry handling: if the user knows there are R seconds remaining until the rally LAUNCHES (start marching), then `created_ts = now - (300 - R)`. If instead they provide L seconds remaining until LANDING, then `created_ts = now - (300 + effective_march_time - L)`; the UI must pick one modality and convert before sending to backend so only `created_ts` is stored.
- Effective march_time chosen via the pet logic described above.
- Validation: if derived prep time used (now - created_ts) > 300 or < 0, reject (invalid input).

API endpoints (sketch)
- GET /api/rallystore -> return full `data.json` (or summary)
- POST /api/players -> create player (body: name, march_time_seconds, pet_status, pet_activated_at)
- PUT /api/players/{id} -> update
- DELETE /api/players/{id}
- POST /api/rallies -> create rally (owner_player_id, launch_ts or relative_to + offset)
- PUT /api/rallies/{id} -> update
- DELETE /api/rallies/{id}
- GET /api/arrival-pattern?window=300 -> compute and return sorted arrival offsets and grouping pattern

Server-side arrival computation
1. For each rally in `rallies` compute landing_ts = launch_ts + 300 + effective_march_time (apply pets)
2. Compute offsets relative to earliest landing in the set (landing_ts - earliest_ts)
3. Create sorted list of offsets (in seconds, floored) and then produce grouping pattern: e.g., [0,0,1,1,2,2]
4. Include mapping back to player/rally so UI can show which player is hitting which offset and when to trigger a sound button

UI changes (front-end wiring)
- Update existing JS to fetch `/api/rallystore` on load and populate UI.
- Add forms to create players and rallies (choose absolute launch time or relative to existing rally)
- Add live countdown display with seconds until landing and overall pattern display
- Add small "use in countdown bot" button to push a chosen pattern to server or kick the bot with HTTP /api/play request later

Edge cases & constraints
- Data validation: if `data.json` schema mismatch, return 400 and error page (for now). We'll add graceful migration later.
- Timezones: store all times as Unix epoch seconds in UTC. Let front-end display localized times.
- Concurrent edits: optimistic concurrency is fine for first pass (no locking).

Clarifying questions (before I code)
1. Pet speed modifier: what is the reduction in march_time when pets are active? (absolute seconds or percentage)
Allow a separate section that we can set a march time with and without pets.


2. Should `launch_ts` be allowed to be either a future timestamp or a "seconds until launch" value? Prefer canonical unix epoch for storage.
3. For relative rallies: do we reference `relative_to` by rally id or by player id (rally id is preferable)?
4. Should players have persistent UUIDs or can we generate short incremental IDs? UUIDs recommended.
5. Do you want server to emit a webhook or call the countdown bot when a countdown is scheduled? (TBD)
6. Does the front-end have any JavaScript frameworks (the `rallytracker/js` content) that I should align with? I'll inspect it after you confirm.

Implementation tasks I will perform after clarifications
1. Create `rally_store.py` with safe read/write and validation.
2. Add REST endpoints in `web_server.py` mirroring the spec.
3. Adapt `rallytracker/js` minimal wiring to call the endpoints and show the pattern output.
4. Add unit tests for computation.
5. Document how to use and example `data.json`.

If this plan looks good, answer the clarifying questions and I will start implementing `rally_store.py` and the API endpoints.

---
### Realtime Sync Strategy (All Three Methods Supported)
We will implement three interchangeable client sync strategies; **long polling** is the default.

1. Short Polling (fallback / simplest)
	- Endpoint: `GET /api/rally/changes/short?since=<seq>` (immediate return; client adds its own interval, e.g. 5 s).
	- Use case: very old browsers, environments where hanging connections are proxied/terminated aggressively.
2. Long Polling (default)
	- Endpoint: `GET /api/rally/changes?since=<seq>&timeout=25`.
	- Server holds request until new events or timeout; returns events or heartbeat.
3. Server-Sent Events (SSE)
	- Endpoint: `GET /api/rally/stream` (response `text/event-stream`).
	- Push each event as `event: change` / `data: {...}`; send keepalive comment every ~20 s.

Client selection logic
```
preferred = localStorage.getItem('syncMode') || 'long-poll';
if (preferred === 'sse' && EventSource supported) use SSE;
else if (preferred === 'long-poll') use long poll;
else fallback to short poll.
```

Server shared components
- Single event dispatcher increments `seq` and broadcasts to:
  - Waiting long-poll coroutines.
  - SSE listeners list.
- Short-poll simply queries latest events > since.

Event retention
- Retain last N events (configurable; start with 500). If `since < current_seq - N`, respond with `full_reset:true` and the snapshot.

Payload harmonization
- All methods produce identical event JSON objects so the same `applyEvents()` JS function works across modes.

Failure / retry
- Long poll: on network error, exponential backoff (0.5s,1s,2s,5s) then resume.
- SSE: auto-reconnect using browser EventSource default, track last `seq` in `Last-Event-ID` header (we will set `id:` line for each event).
- Short poll: keep static interval (configurable) or escalate to long poll if user switches.

Metrics (future)
- Count active long-poll waiters, SSE clients, average wake latency.

Security placeholder
- Option later to require an auth token header for mutation endpoints; read endpoints can stay open if desired.

Implementation order
1. Event bus + long polling.
2. SSE layer (thin wrapper atop bus).
3. Short poll lightweight endpoint.
4. Front-end selection UI (dropdown: Auto / Long Poll (default) / SSE / Short Poll).

Default mode justification: long polling provides low idle overhead, broadly compatible, simpler resource management vs many always-open SSE streams if scale increases.