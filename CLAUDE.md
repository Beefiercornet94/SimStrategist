# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SimStrategist is a Flask-based web application that displays and analyzes live in-game telemetry from racing simulators. It currently supports F1 (2022/2023/2024) and has placeholder support for Le Mans Ultimate (LMU).

## Commands

### Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run the Flask web server
python3 app.py

# Run the F1 UDP telemetry listener (separate process)
python3 f1/server.py
```

### Database Setup

SQL schema files are in `queries/`. To reset the database:
```bash
sqlite3 strategist.db < queries/create_users.sqlite3-query
sqlite3 strategist.db < queries/create_games.sqlite3-query
sqlite3 strategist.db < queries/create_sessions.sqlite3-query
```

## Architecture

The app has two independently running components:

1. **Flask web server** (`app.py`) — handles HTTP routes, user auth, and templating
2. **F1 UDP listener** (`f1/server.py`) — listens on UDP port 20777 for binary telemetry packets from the F1 game

Telemetry data flows: F1 game → UDP packets → `f1/server.py` (binary struct parsing) → `f1/telemetry_state.py` (thread-safe singleton with numpy circular buffers) → Flask routes → Jinja2 templates.

### Key Files

- `app.py` — Flask routes: `/`, `/login`, `/register`, `/logout`, `/setup`
- `helpers.py` — `login_required` decorator and `apology()` error renderer
- `f1/config.py` — UDP settings (port 20777), performance tuning, UI colors
- `f1/server.py` — `UdpListener` class: parses F1 23/24 binary packet format (session, lap data, car telemetry)
- `f1/telemetry_state.py` — Thread-safe singleton with pre-allocated numpy circular buffers for telemetry history
- `lmu/` — LMU support is not yet implemented (placeholder files only)

### Database

SQLite (`strategist.db`) via the `cs50.SQL` wrapper. Three tables: `users`, `games`, `sessions`. The `games` table is pre-populated with F1-2022/23/24 and LMU entries.

### Templates

Jinja2 + Bootstrap 5.3. `templates/layout.html` is the base. Note: `templates/setup.html` is referenced in `app.py` but does not yet exist.

## External Code Attribution

Per README:
- F1 telemetry parsing adapted from [Harmitx7's F1-TELEMETRY-DASHBOARD](https://github.com/Harmitx7)
- LMU telemetry JSON module from community.lemansultimate.com forums
- Auth routes and templates adapted from CS50 Finance
