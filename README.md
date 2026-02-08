# WOS Rally Sync

This folder contains files for a **single Cloudflare Worker** that:
- serves the built Vite frontend (Workers Assets)
- provides a **WebSocket backend** using a **Durable Object** (one room per `instance_id`)

## Requirements

- Node.js 20.19+ or 22.12+ (required by Vite)
- npm

## Local dev

1) Install deps:
```bash
npm install
npm --prefix web install
```

2) Run the backend (Worker) locally:
```bash
npm run dev
```
This starts `wrangler dev` on `http://localhost:8787`.

3) Run the frontend (Vite) in a second terminal:
```bash
npm run dev:web
```
Open the Vite URL (usually `http://localhost:5173`).

The frontend will auto-connect to the local Worker at `ws://localhost:8787/ws?instance_id=...`.

## Tests

Run timing + scenario tests for the web client:
```bash
npm run test:web
```

## Deploy to Cloudflare (recommended: one Worker)

1) Authenticate:
```bash
npx wrangler login
```

2) Deploy:
```bash
npm run deploy
```

This builds the Vite app into `web/dist` and deploys the Worker + assets.

## Discord Activity

Discord Activities loads your URL in an iframe and provide an `instance_id` query param.
This project uses:
- `?instance_id=...` as the multiplayer room id
- WebSockets on the same origin: `/ws?instance_id=...`

To setup the discord activity:

1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Choose your Application
3. Go to "Activities - Settings":
   - Check "Enable Activities"
   - Check "Supported Platforms" for Web, iOS, Android
4. Go to "Activities URL Mappings":
   - prefix `/` ; target: `wos-rally-sync.yourdomain.workers.dev`
5. (Optional) Set custom Background/Coverart at "Activities - Art Assets"


### Important settings
- Ensure your Activity is allowed to use WebSockets.

## Protocol (client <-> server)

Client sends:
- `STATE_REQUEST`
- `PLAYER_ADD`
- `PLAYER_REMOVE`
- `RALLY_START` (`{ starterId, rallyDurationMs, preDelayMs }` or `{ starterId, launchAt }`)
- `RALLY_END`
- `TIME_SYNC_REQUEST` (`{ t0 }`)

Server broadcasts:
- `{ type: "STATE", payload: { players, rally } }`
- `TIME_SYNC_RESPONSE` (`{ t0, t1, t2 }`)
