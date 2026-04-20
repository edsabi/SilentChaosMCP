# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Silent Chaos is a real-time multiplayer submarine warfare simulation. Players/bots control submarines in a 2D world with physics, sonar, torpedoes, and tactical gameplay.

## Running the Server

```bash
cd Silent-Chaos
pip install -r requirements.txt

# Start server (default: http://localhost:5000)
python server_world_db.py

# Start with an admin account
python server_world_db.py --username admin --password mysecret

# Other flags: --host, --port, --enable-logging, --disable-logging, --logging-hz
```

## Running Bots

```bash
# Start 5 battle-royale bots against localhost
python bots/apex_brain_battle_royale.py http://localhost:5000 5
```

## Architecture

The entire server lives in a single file: `Silent-Chaos/server_world_db.py` (~5000 lines). There is no build step—this is vanilla Python + Flask.

### Core Systems

**Game Loop (10 Hz)** runs in a dedicated background thread:
1. Load submarines and drones from SQLite DB
2. Apply physics (position, depth, heading, battery drain)
3. Collision detection → explosions, damage
4. Schedule sonar contacts (passive/active)
5. Commit state to DB
6. Fan-out SSE events to connected clients

**Database Models** (SQLAlchemy, SQLite with WAL mode):
- `User` / `ApiKey` — authentication
- `SubModel` — submarine physics state (position, depth, heading, velocity, battery, health, magazine slots)
- `TorpedoModel` / `DroneModel` — projectiles with 4 payload types: explosive, detection, decoy, EMP
- `FuelerModel` — NPC refueling stations

**Event System**: SSE endpoint `/stream` delivers per-user event queues. Event types: `snapshot`, `contact` (passive sonar), `echo` (active ping return), `explosion`, `torpedo_contact`, `detection_drone_bearing`.

**Configuration**: ~179 `DEFAULT_CFG` keys in `server_world_db.py`. Override any key via `game_config.json` placed in the project root (deep-merged at startup).

### API

50+ REST endpoints. Key groups:
- Auth: `/signup`, `/login`
- Game state: `/state`, `/register_sub`, `/public`, `/rules`, `/leaderboard`
- Submarine control: `/control/<sub_id>`, `/set_sub_heading/<sub_id>`, `/turn_sub/<sub_id>`, `/snorkel/<sub_id>`, `/emergency_blow/<sub_id>`
- Drones/torpedoes: `/launch_drone/<sub_id>`, `/reload_drones/<sub_id>`, `/set_torp_homing/<torp_id>`, `/set_torp_heading/<torp_id>`, `/torp_ping/<torp_id>`
- Sonar: `/ping/<sub_id>`, `/set_passive_array/<sub_id>`, `/weather_scan/<sub_id>`
- Admin: `/admin_ui`, `/admin/perf`, `/admin/state`, `/admin/logs`

Full reference: `Silent-Chaos/docs/API_REFERENCE.md`

### Frontend

Vanilla HTML5/JS — no framework, no build step:
- `ui.html` — main player UI
- `ui_mobile.html` — mobile-responsive UI
- `admin_ui.html` — admin dashboard (battlefield view, logs, replay/GIF export)
- `leaderboard.html` — scoring display

### Bots

`bots/apex_brain_battle_royale.py` — primary bot implementation with three classes:
- `SubBrawlClient` — HTTP/SSE client wrapper around the REST API
- `BattleRoyaleAccount` — single-bot state machine and tactics
- `BattleRoyaleManager` — spawns and manages multiple bot instances

Bot development guide: `Silent-Chaos/docs/BOT_DEV_GUIDE.md`

### Thread Safety

World state is protected by an `RLock`. The game loop holds the lock for the full tick. API handlers acquire it for reads/writes. Performance metrics (physics time, DB commit time, lock contention) are exposed at `/admin/perf`.

### Logging / Replay

Pass `--enable-logging` to record full world state as JSONL in `logs/`. The admin UI can replay logs and export animated GIFs.
