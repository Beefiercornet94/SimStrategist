# SimStrategist — Developer Usage Guide

## What is this?

SimStrategist is a Flask web app that displays and analyses live in-game telemetry from racing simulators. It currently supports **F1 2022/2023/2024** (via binary UDP packets) and has placeholder support for **Le Mans Ultimate** (LMU, via JSON over TCP/UDP).

A ChatGPT-powered AI strategy analyser is also built in, using real-time weather and tyre data to recommend pit strategies.

---

## Architecture Overview

Two independent processes must run simultaneously:

```text
F1 game ──UDP:20777──▶ f1/server.py ──▶ f1/telemetry_state.py ──▶ app.py API routes ──▶ browser
                        (binary parse)     (thread-safe singleton)   (SSE / JSON)
```

```text
LMU game ──TCP:5100──▶ lmu/server.py ──▶ lmu/telemetry_state.py ──▶ app.py API routes ──▶ browser
                        (JSON parse)       (thread-safe singleton)
```

Both listeners run as **daemon threads inside `app.py`** — you only need to start one process. However, `f1/server.py` can also be run standalone (useful when recording).

### Key files

| File | Role |
| ---- | ---- |
| `app.py` | Flask app, starts background threads, defines all HTTP routes |
| `f1/server.py` | Parses binary F1 UDP packets; optionally records them |
| `f1/telemetry_state.py` | Thread-safe singleton with numpy circular buffers |
| `f1/config.py` | UDP settings, buffer sizes, UI colours |
| `f1/recorder.py` | Standalone UDP sniffer — saves packets to a `.f1rec` file |
| `f1/replayer.py` | Reads a `.f1rec` file and replays packets over UDP |
| `strategy/ai_strategy.py` | Calls OpenAI API to generate 3 race strategies |
| `strategy/weather_history.py` | Records weather samples every 10 s during a session |
| `lmu/server.py` | JSON-over-TCP/UDP listener for Le Mans Ultimate |

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialise the database

Only needed once (or to reset):

```bash
sqlite3 strategist.db < queries/create_users.sqlite3-query
sqlite3 strategist.db < queries/create_games.sqlite3-query
sqlite3 strategist.db < queries/create_sessions.sqlite3-query
```

### 3. Set the OpenAI API key (for AI strategy)

```bash
export OPENAI_API_KEY=your-key-here
```

Without this the `/api/strategy/ai` endpoint will return an error, but everything else works fine.

### 4. Run the app

```bash
python3 app.py
```

Open [http://localhost:5051](http://localhost:5051). Register an account, then go to `/setup` to configure your game.

> **Port**: defaults to `5051`. Override with `PORT=8080 python3 app.py`.
> **F1 game setting**: in-game go to *Settings → Telemetry Settings* and set the UDP IP to your machine's IP and port to `20777`.

---

## API Routes

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/api/telemetry` | Single JSON snapshot of current state |
| `GET` | `/api/telemetry/stream?game=f1\|lmu` | Server-Sent Events stream (~60 Hz) |
| `GET` | `/api/weather/history?game=f1\|lmu` | Weather history list for this session |
| `POST` | `/api/strategy/ai` | Trigger AI strategy analysis (body: `{"game":"f1"}`) |

### Telemetry snapshot shape

```json
{
  "connected": true,
  "telemetry": {
    "speed": 287, "throttle": 0.94, "brake": 0.0,
    "gear": 7, "rpm": 11450, "drs": 1,
    "tyre_visual_compound": 16,
    "tyre_age_laps": 12, "fuel_in_tank": 28.4,
    "fuel_remaining_laps": 14.2,
    "engine_temp": 102, "tyres_surface_temp": [88, 89, 90, 91]
  },
  "lap_data": {
    "current_lap": 5, "current_lap_time": 82450,
    "last_lap_time": 83120, "best_lap_time": 82800,
    "car_position": 3, "pit_status": 0,
    "lap_distance": 1247.3
  },
  "session": {
    "track_id": 10, "session_type": 10,
    "total_laps": 57, "weather": 0,
    "track_temperature": 38, "air_temperature": 24
  }
}
```

---

## Recording & Replaying Telemetry

The recording system lets you capture a real game session and replay it later for development without needing the game running.

### File format: `.f1rec`

A compact binary format:

```text
Bytes 0–15  : Header — magic b'F1REC\x00', version uint8, 9 reserved bytes
Per packet  : float64 timestamp (seconds since start)
              uint16  packet length
              N bytes raw UDP data
```

Packets are stored as raw, unmodified UDP datagrams — the full parsing pipeline runs normally during replay.

---

### Option A — Record while the server is processing live data

Run `f1/server.py` directly with `--record`:

```bash
cd f1
python3 server.py --record ../example-data/myrace.f1rec
```

Press `Ctrl+C` to stop. The file is flushed and closed cleanly.

---

### Option B — Standalone recorder (pure sniffer, no state updates)

Use this if you want to capture packets without any processing, or if you want to record and forward to another machine.

```bash
python3 f1/recorder.py example-data/myrace.f1rec
python3 f1/recorder.py example-data/myrace.f1rec --port 20777
```

---

### Replaying a recording

Start the Flask app first (`python3 app.py`), then in a second terminal:

```bash
# Real-time replay (1x speed)
python3 f1/replayer.py example-data/myrace.f1rec

# Fast replay — great for testing state accumulation quickly
python3 f1/replayer.py example-data/myrace.f1rec --speed 4.0

# Maximum speed (no timing — floods all packets instantly)
python3 f1/replayer.py example-data/myrace.f1rec --speed 0

# Loop continuously — useful when developing the UI
python3 f1/replayer.py example-data/myrace.f1rec --loop

# All options
python3 f1/replayer.py example-data/myrace.f1rec --speed 2.0 --loop --host 127.0.0.1 --port 20777
```

The replayer sends packets to the local UDP port, so the app processes them exactly as if the game were running live.

---

## How telemetry flows (step by step)

1. **F1 game** sends binary UDP datagrams to port `20777` at ~20 Hz.
2. **`UdpListener`** (`f1/server.py`) receives each datagram, reads the 24-byte header to find the `packet_id` and `player_car_index`, then calls the appropriate `F1PacketParser` static method.
3. The parsed dict is passed to `state.update_telemetry()` / `update_lap_data()` / `update_session()` in **`TelemetryState`** (`f1/telemetry_state.py`).
4. `TelemetryState` holds the latest values plus a **numpy circular buffer** (2400 points = 120 s at 20 Hz) for history charts.
5. **`app.py`** exposes `/api/telemetry/stream` as a **Server-Sent Events** endpoint. It polls `state.last_update_time` every 16 ms and pushes a JSON snapshot whenever new data arrives.
6. The browser receives SSE events and updates the live dashboard without polling.

### Why `use_reloader=False`?

Flask's reloader forks the process, which would start duplicate UDP listener threads. `use_reloader=False` prevents this.

---

## Telemetry state internals

`TelemetryState` is a **singleton** — `TelemetryState()` always returns the same instance regardless of where it is called. It uses a `threading.Lock` around all reads and writes.

The circular buffer uses pre-allocated `numpy` arrays instead of `deque` for ~50% lower memory usage. When the buffer is full, the oldest entry is overwritten. `get_history_df()` handles the wrap-around when constructing the `DataFrame`.

```text
history_index ──▶  [  old  |  new  |  newest  |  oldest  |  ... ]
                    ^write position; wraps to 0 when it reaches maxlen
```

---

## AI Strategy

`/api/strategy/ai` calls `strategy/ai_strategy.py`, which:

1. Takes a snapshot of the current telemetry + weather history.
2. Builds a structured prompt and calls `gpt-4o-mini` via the OpenAI SDK.
3. Returns three strategies: **Standard**, **Push**, and **Fuel-save**, each with stop laps, compounds, and estimated time delta.

Requires `OPENAI_API_KEY` to be set.

---

## Common issues

| Problem | Likely cause |
| ------- | ------------ |
| Dashboard shows "Disconnected" | Game not sending to port 20777, or firewall blocking UDP |
| `Address already in use` on startup | Another process is on 5051; set `PORT=xxxx` env var |
| AI strategy returns error | `OPENAI_API_KEY` not set or invalid |
| Replay has no effect on dashboard | App not running, or replaying to wrong port |
| Recording stops mid-session | Disk full, or `Ctrl+C` — recordings flush on clean exit |
