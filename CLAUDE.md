# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SimStrategist is a Flask-based web application that displays and analyzes live in-game telemetry from racing simulators. It supports F1 (2018–2024), Forza Horizon 4/5, and Le Mans Ultimate (LMU, partially implemented).

## Commands

### Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Set Claude API key (required for AI strategy)
export ANTHROPIC_API_KEY=your_key_here

# Run the Flask web server (starts all listeners as daemon threads internally)
python3 app.py
```

All telemetry listeners (F1, LMU, Forza) are started as daemon threads inside `app.py` — there is no separate server script to run.

### Recording & Replay (F1)

```bash
# Record raw F1 UDP packets to a .f1rec file
python3 f1/recorder.py

# Replay a .f1rec file (supports --speed and --loop flags)
python3 f1/replayer.py path/to/file.f1rec --speed 2.0 --loop
```

### Database Setup

SQL schema files are in `queries/`. To reset the database:

```bash
sqlite3 strategist.db < queries/create_users.sqlite3-query
sqlite3 strategist.db < queries/create_games.sqlite3-query
sqlite3 strategist.db < queries/create_sessions.sqlite3-query
```

## Architecture

All telemetry listeners run as daemon threads inside the Flask process. The app is a single process.

Telemetry data flow (same pattern for all games):
`Game → UDP/TCP packets → server.py (binary/JSON parsing) → telemetry_state.py (thread-safe singleton, numpy circular buffers) → Flask API routes → SSE stream → browser JavaScript`

### Routes

- `GET /` — Home page with F1 2025 race countdown
- `GET /telemetry` — Live telemetry dashboard
- `GET /strategy` — AI strategy co-pilot
- `GET /setup` — Game configuration page
- `GET /api/telemetry` — JSON snapshot of current telemetry
- `GET /api/telemetry/stream` — Server-Sent Events stream (~60 Hz)
- `GET /api/weather/history` — Weather history for current session
- `POST /api/strategy/ai` — Trigger AI strategy analysis (calls Claude API)
- `POST /api/record/start` / `POST /api/record/stop` / `GET /api/record/status` — Recording control
- `GET /api/f1/next-session` — Next F1 2025 session countdown data

### Key Files

- `app.py` — Flask routes, daemon thread startup, F1 2025 schedule, weather sampling
- `helpers.py` — `login_required` decorator and `apology()` error renderer
- `strategy/ai_strategy.py` — Calls Claude API; returns Standard/Push/Save strategy JSON
- `strategy/weather_history.py` — `WeatherHistory` singleton; records weather snapshots per game
- `f1/server.py` — `UdpListener` + `F1PacketParser`; parses F1 2018–2024 binary UDP (port 20777); supports recording to `.f1rec`
- `f1/telemetry_state.py` — Thread-safe singleton with numpy circular buffers (2400 points)
- `f1/config.py` — UDP settings, performance tuning, UI color constants
- `f1/recorder.py` — Standalone UDP sniffer; saves `.f1rec` binary files
- `f1/replayer.py` — Replays `.f1rec` files to UDP with speed/loop control
- `lmu/server.py` — `TcpListener`; receives JSON from LMU telemetry plugin (port 5100); recording support
- `lmu/telemetry_state.py` — Mirrors F1 interface; circular buffers (600 points, ~10s at 60 Hz)
- `forza_hrzn/server.py` — `UdpListener`; auto-detects FH4 (port 20044, 324 bytes) vs FH5 (port 20055, 323 bytes)
- `forza_hrzn/telemetry_state.py` — Mirrors F1 interface; 7200-point buffers (120s at 60 Hz)
- `forza_hrzn/config.py` — UDP ports and buffer settings for FH4/FH5

### Static Assets

All JavaScript lives in `static/scripts/` — never inline JS in HTML templates.

- `telemetry.js` — SSE handler, game family detection (F1/LMU/Forza), live dashboard updates, LMU class ring
- `strategy.js` — Fetches and renders AI strategy recommendations, weather graph, pit stop tables
- `input-trace.js` — Driver inputs visualization (bar + scrolling graph modes)
- `f1-countdown.js` — F1 2025 countdown, polls `/api/f1/next-session`
- `setup.js` — Game configuration form handler
- `theme-init.js` — Dark/light theme initialization (runs early to prevent FOUC)

### Database

SQLite (`strategist.db`) via the `cs50.SQL` wrapper. Three tables: `users`, `games`, `sessions`. The `games` table is pre-populated with F1-2022/23/24 and LMU entries.

### Templates

Jinja2 + Bootstrap 5.3. `templates/layout.html` is the base template. All pages: `index.html`, `telemetry.html`, `strategy.html`, `setup.html`, `apology.html`.

## Implementation Status

| Feature | Status |
|---|---|
| F1 2018–2024 UDP telemetry | Complete |
| Forza Horizon 4/5 UDP telemetry | Complete |
| Le Mans Ultimate JSON telemetry | Partial (server.py works; other modules are stubs) |
| Forza Motorsport | Not started (empty directory) |
| Live telemetry dashboard | Complete |
| AI strategy analysis (Claude API) | Complete |
| F1 2025 race countdown | Complete |
| Recording / replay | Complete (F1); partial (LMU) |
| User auth & database | Complete |
| Setup page | Complete |

## External Code Attribution

Per README:
- F1 telemetry parsing adapted from [Harmitx7's F1-TELEMETRY-DASHBOARD](https://github.com/Harmitx7)
- LMU telemetry JSON module from community.lemansultimate.com forums
- Auth routes and templates adapted from CS50 Finance
