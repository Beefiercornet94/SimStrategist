#---------- SETUP / CONFIG ----------#

# Import requirements
import json
import os
import threading
import time

from cs50 import SQL
from flask import Flask, Response, jsonify, redirect, render_template, request, session, stream_with_context
from flask_session import Session

from f1.server import UdpListener
from f1.telemetry_state import state as f1_state

from lmu.server import TcpListener as LmuTcpListener
from lmu.telemetry_state import state as lmu_state

from forza_hrzn.server import UdpListener as ForzaHrznUdpListener
from forza_hrzn.telemetry_state import state as forza_hrzn_state

from strategy.weather_history import weather_history
from strategy.ai_strategy import analyze_strategy


# Configure application
app = Flask(__name__)

# Listeners run as daemon threads inside this process so a single `python3 app.py`
# starts everything. use_reloader=False (bottom of file) prevents Flask's dev
# reloader from forking and spawning duplicate listener threads.
_udp_listener = UdpListener()
_udp_listener.start()

_lmu_listener = LmuTcpListener()
_lmu_listener.start()

_forza_hrzn_listener = ForzaHrznUdpListener()
_forza_hrzn_listener.start()

# Samples weather from the live telemetry state every 10 s so the AI strategist
# has a complete picture of how conditions evolved over the race.
def _weather_sampler():
    while True:
        try:
            f1_snap = f1_state.get_snapshot()
            if f1_snap['connected']:
                s   = f1_snap['session']
                lap = f1_snap['lap_data'].get('current_lap', 0) or 0
                weather_history.record(
                    'f1', lap,
                    s.get('weather', 0),
                    s.get('track_temperature', 0),
                    s.get('air_temperature', 0),
                )

            lmu_snap = lmu_state.get_snapshot()
            if lmu_snap['connected']:
                s   = lmu_snap['session']
                lap = lmu_snap['lap_data'].get('current_lap', 0) or 0
                flag = (s.get('flag') or '').lower()
                weather_history.record(
                    'lmu', lap,
                    3 if 'rain' in flag else 0,
                    s.get('track_temp', 0),
                    s.get('ambient_temp', 0),
                )
        except Exception:
            pass
        time.sleep(10)

_sampler = threading.Thread(target=_weather_sampler, daemon=True)
_sampler.start()

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///strategist.db")

@app.after_request
def after_request(response):
    # Ensure responses aren't cached
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = "0"
    response.headers["Pragma"] = "no-cache"
    return response



#---------- INDEX ----------#

@app.route("/")
def index():
    return render_template("index.html")


#---------- F1 SCHEDULE ----------#

import datetime

_F1_2025_SCHEDULE = [
    {"round": 1, "grandPrix": "Australian Grand Prix", "circuit": "Albert Park Grand Prix Circuit", "country": "Australia", "sessions": {"practice1": "2025-03-14T01:30:00Z", "practice2": "2025-03-14T05:00:00Z", "practice3": "2025-03-15T01:30:00Z", "qualifying": "2025-03-15T05:00:00Z", "race": "2025-03-16T04:00:00Z"}},
    {"round": 2, "grandPrix": "Chinese Grand Prix", "circuit": "Shanghai International Circuit", "country": "China", "sessions": {"practice1": "2025-03-21T03:30:00Z", "sprintQualifying": "2025-03-21T07:30:00Z", "sprintRace": "2025-03-22T03:00:00Z", "qualifying": "2025-03-22T07:00:00Z", "race": "2025-03-23T07:00:00Z"}},
    {"round": 3, "grandPrix": "Japanese Grand Prix", "circuit": "Suzuka Circuit", "country": "Japan", "sessions": {"practice1": "2025-04-04T02:30:00Z", "practice2": "2025-04-04T06:00:00Z", "practice3": "2025-04-05T02:30:00Z", "qualifying": "2025-04-05T06:00:00Z", "race": "2025-04-06T05:00:00Z"}},
    {"round": 4, "grandPrix": "Bahrain Grand Prix", "circuit": "Bahrain International Circuit", "country": "Bahrain", "sessions": {"practice1": "2025-04-11T11:30:00Z", "practice2": "2025-04-11T15:00:00Z", "practice3": "2025-04-12T12:30:00Z", "qualifying": "2025-04-12T16:00:00Z", "race": "2025-04-13T15:00:00Z"}},
    {"round": 5, "grandPrix": "Saudi Arabian Grand Prix", "circuit": "Jeddah Corniche Circuit", "country": "Saudi Arabia", "sessions": {"practice1": "2025-04-18T13:30:00Z", "practice2": "2025-04-18T17:00:00Z", "practice3": "2025-04-19T13:30:00Z", "qualifying": "2025-04-19T17:00:00Z", "race": "2025-04-20T17:00:00Z"}},
    {"round": 6, "grandPrix": "Miami Grand Prix", "circuit": "Miami International Autodrome", "country": "United States", "sessions": {"practice1": "2025-05-02T16:30:00Z", "sprintQualifying": "2025-05-02T20:30:00Z", "sprintRace": "2025-05-03T16:00:00Z", "qualifying": "2025-05-03T20:00:00Z", "race": "2025-05-04T20:00:00Z"}},
    {"round": 7, "grandPrix": "Emilia Romagna Grand Prix", "circuit": "Autodromo Enzo e Dino Ferrari", "country": "Italy", "sessions": {"practice1": "2025-05-16T11:30:00Z", "practice2": "2025-05-16T15:00:00Z", "practice3": "2025-05-17T10:30:00Z", "qualifying": "2025-05-17T14:00:00Z", "race": "2025-05-18T13:00:00Z"}},
    {"round": 8, "grandPrix": "Monaco Grand Prix", "circuit": "Circuit de Monaco", "country": "Monaco", "sessions": {"practice1": "2025-05-23T11:30:00Z", "practice2": "2025-05-23T15:00:00Z", "practice3": "2025-05-24T10:30:00Z", "qualifying": "2025-05-24T14:00:00Z", "race": "2025-05-25T13:00:00Z"}},
    {"round": 9, "grandPrix": "Spanish Grand Prix", "circuit": "Circuit de Barcelona-Catalunya", "country": "Spain", "sessions": {"practice1": "2025-05-30T11:30:00Z", "practice2": "2025-05-30T15:00:00Z", "practice3": "2025-05-31T10:30:00Z", "qualifying": "2025-05-31T14:00:00Z", "race": "2025-06-01T13:00:00Z"}},
    {"round": 10, "grandPrix": "Canadian Grand Prix", "circuit": "Circuit Gilles Villeneuve", "country": "Canada", "sessions": {"practice1": "2025-06-13T17:30:00Z", "practice2": "2025-06-13T21:00:00Z", "practice3": "2025-06-14T16:30:00Z", "qualifying": "2025-06-14T20:00:00Z", "race": "2025-06-15T18:00:00Z"}},
    {"round": 11, "grandPrix": "Austrian Grand Prix", "circuit": "Red Bull Ring", "country": "Austria", "sessions": {"practice1": "2025-06-27T11:30:00Z", "practice2": "2025-06-27T15:00:00Z", "practice3": "2025-06-28T10:30:00Z", "qualifying": "2025-06-28T14:00:00Z", "race": "2025-06-29T13:00:00Z"}},
    {"round": 12, "grandPrix": "British Grand Prix", "circuit": "Silverstone Circuit", "country": "United Kingdom", "sessions": {"practice1": "2025-07-04T11:30:00Z", "practice2": "2025-07-04T15:00:00Z", "practice3": "2025-07-05T10:30:00Z", "qualifying": "2025-07-05T14:00:00Z", "race": "2025-07-06T14:00:00Z"}},
    {"round": 13, "grandPrix": "Belgian Grand Prix", "circuit": "Circuit de Spa-Francorchamps", "country": "Belgium", "sessions": {"practice1": "2025-07-25T10:30:00Z", "sprintQualifying": "2025-07-25T14:30:00Z", "sprintRace": "2025-07-26T10:00:00Z", "qualifying": "2025-07-26T14:00:00Z", "race": "2025-07-27T13:00:00Z"}},
    {"round": 14, "grandPrix": "Hungarian Grand Prix", "circuit": "Hungaroring", "country": "Hungary", "sessions": {"practice1": "2025-08-01T11:30:00Z", "practice2": "2025-08-01T15:00:00Z", "practice3": "2025-08-02T10:30:00Z", "qualifying": "2025-08-02T14:00:00Z", "race": "2025-08-03T13:00:00Z"}},
    {"round": 15, "grandPrix": "Dutch Grand Prix", "circuit": "Circuit Park Zandvoort", "country": "Netherlands", "sessions": {"practice1": "2025-08-29T10:30:00Z", "practice2": "2025-08-29T14:00:00Z", "practice3": "2025-08-30T09:30:00Z", "qualifying": "2025-08-30T13:00:00Z", "race": "2025-08-31T13:00:00Z"}},
    {"round": 16, "grandPrix": "Italian Grand Prix", "circuit": "Autodromo Nazionale di Monza", "country": "Italy", "sessions": {"practice1": "2025-09-05T11:30:00Z", "practice2": "2025-09-05T15:00:00Z", "practice3": "2025-09-06T10:30:00Z", "qualifying": "2025-09-06T14:00:00Z", "race": "2025-09-07T13:00:00Z"}},
    {"round": 17, "grandPrix": "Azerbaijan Grand Prix", "circuit": "Baku City Circuit", "country": "Azerbaijan", "sessions": {"practice1": "2025-09-19T08:30:00Z", "practice2": "2025-09-19T12:00:00Z", "practice3": "2025-09-20T08:30:00Z", "qualifying": "2025-09-20T12:00:00Z", "race": "2025-09-21T11:00:00Z"}},
    {"round": 18, "grandPrix": "Singapore Grand Prix", "circuit": "Marina Bay Street Circuit", "country": "Singapore", "sessions": {"practice1": "2025-10-03T09:30:00Z", "practice2": "2025-10-03T13:00:00Z", "practice3": "2025-10-04T09:30:00Z", "qualifying": "2025-10-04T13:00:00Z", "race": "2025-10-05T12:00:00Z"}},
    {"round": 19, "grandPrix": "United States Grand Prix", "circuit": "Circuit of the Americas", "country": "United States", "sessions": {"practice1": "2025-10-17T17:30:00Z", "sprintQualifying": "2025-10-17T21:30:00Z", "sprintRace": "2025-10-18T17:00:00Z", "qualifying": "2025-10-18T21:00:00Z", "race": "2025-10-19T19:00:00Z"}},
    {"round": 20, "grandPrix": "Mexico City Grand Prix", "circuit": "Autódromo Hermanos Rodríguez", "country": "Mexico", "sessions": {"practice1": "2025-10-24T18:30:00Z", "practice2": "2025-10-24T22:00:00Z", "practice3": "2025-10-25T17:30:00Z", "qualifying": "2025-10-25T21:00:00Z", "race": "2025-10-26T20:00:00Z"}},
    {"round": 21, "grandPrix": "São Paulo Grand Prix", "circuit": "Autódromo José Carlos Pace", "country": "Brazil", "sessions": {"practice1": "2025-11-07T14:30:00Z", "sprintQualifying": "2025-11-07T18:30:00Z", "sprintRace": "2025-11-08T14:00:00Z", "qualifying": "2025-11-08T18:00:00Z", "race": "2025-11-09T17:00:00Z"}},
    {"round": 22, "grandPrix": "Las Vegas Grand Prix", "circuit": "Las Vegas Strip Street Circuit", "country": "United States", "sessions": {"practice1": "2025-11-21T00:30:00Z", "practice2": "2025-11-21T04:00:00Z", "practice3": "2025-11-22T00:30:00Z", "qualifying": "2025-11-22T04:00:00Z", "race": "2025-11-23T04:00:00Z"}},
    {"round": 23, "grandPrix": "Qatar Grand Prix", "circuit": "Losail International Circuit", "country": "Qatar", "sessions": {"practice1": "2025-11-28T13:30:00Z", "sprintQualifying": "2025-11-28T17:30:00Z", "sprintRace": "2025-11-29T14:00:00Z", "qualifying": "2025-11-29T18:00:00Z", "race": "2025-11-30T16:00:00Z"}},
    {"round": 24, "grandPrix": "Abu Dhabi Grand Prix", "circuit": "Yas Marina Circuit", "country": "United Arab Emirates", "sessions": {"practice1": "2025-12-05T09:30:00Z", "practice2": "2025-12-05T13:00:00Z", "practice3": "2025-12-06T10:30:00Z", "qualifying": "2025-12-06T14:00:00Z", "race": "2025-12-07T13:00:00Z"}},
]

_SESSION_LABELS = {
    "practice1": "Practice 1",
    "practice2": "Practice 2",
    "practice3": "Practice 3",
    "sprintQualifying": "Sprint Qualifying",
    "sprintRace": "Sprint Race",
    "qualifying": "Qualifying",
    "race": "Race",
}

# Canonical session order within a weekend
_SESSION_ORDER = ["practice1", "practice2", "sprintQualifying", "practice3", "sprintRace", "qualifying", "race"]

@app.route("/api/f1/next-session")
def api_f1_next_session():
    now = datetime.datetime.now(datetime.timezone.utc)
    best = None
    for event in _F1_2025_SCHEDULE:
        for key in _SESSION_ORDER:
            iso = event["sessions"].get(key)
            if not iso:
                continue
            t = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
            if t > now:
                if best is None or t < best["time"]:
                    best = {
                        "time": t,
                        "isoTime": iso,
                        "session": _SESSION_LABELS[key],
                        "grandPrix": event["grandPrix"],
                        "circuit": event["circuit"],
                        "country": event["country"],
                        "round": event["round"],
                    }
                break  # only care about the next session within this event
    if best is None:
        return jsonify({"none": True})
    return jsonify({
        "none": False,
        "isoTime": best["isoTime"],
        "session": best["session"],
        "grandPrix": best["grandPrix"],
        "circuit": best["circuit"],
        "country": best["country"],
        "round": best["round"],
    })



#---------- TELEMETRY / STRATEGY ----------#

def _recording_filename(game: str) -> str:
    """Return an auto-named example-data path for the given game."""
    import datetime
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    ext   = 'f1rec' if game == 'f1' else 'lmurec'
    return f"example-data/{game}_{stamp}.{ext}"

@app.route("/api/telemetry")
def api_telemetry():
    return jsonify(f1_state.get_snapshot())

@app.route("/api/telemetry/stream")
def api_telemetry_stream():
    """
    Server-Sent Events stream for live telemetry.
    Query param: ?game=f1  (default) | ?game=lmu
    Pushes a JSON event on every new data frame; keepalive every 500 ms otherwise.
    """
    game = request.args.get("game", "f1").lower()
    if game == "lmu":
        src = lmu_state
    elif game == "forza_hrzn":
        src = forza_hrzn_state
    else:
        src = f1_state

    def generate():
        last_seen = 0.0
        while True:
            updated = src.last_update_time
            if updated > last_seen:
                # New data arrived — push a snapshot to the browser
                last_seen = updated
                payload = json.dumps(src.get_snapshot())
                yield f"data: {payload}\n\n"
            else:
                # No new data — send an SSE comment to keep the connection alive
                yield ": keepalive\n\n"
            time.sleep(0.016)   # ~60 Hz check rate → ≤16 ms latency

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )

@app.route("/api/weather/history")
def api_weather_history():
    """Return the recorded weather history for the requested game."""
    game = request.args.get("game", "f1").lower()
    return jsonify(weather_history.get_history(game))

@app.route("/api/strategy/ai", methods=["POST"])
def api_strategy_ai():
    """
    Run AI strategy analysis via Claude.
    Body: {"game": "f1"|"lmu"}
    """
    body = request.get_json(silent=True) or {}
    game = body.get("game", request.args.get("game", "f1")).lower()
    try:
        result = analyze_strategy(game)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/record/start", methods=["POST"])
def api_record_start():
    """Start recording telemetry for the given game.
    Body: {"game": "f1"|"lmu"}
    Auto-names the file example-data/{game}_{timestamp}.{ext}
    """
    body = request.get_json(silent=True) or {}
    game = body.get("game", "f1").lower()
    path = _recording_filename(game)
    if game == "lmu":
        _lmu_listener.start_recording(path)
    else:
        _udp_listener.start_recording(path)
    return jsonify({"recording": True, "game": game, "path": path})

@app.route("/api/record/stop", methods=["POST"])
def api_record_stop():
    """Stop any active recording."""
    _udp_listener.stop_recording()
    _lmu_listener.stop_recording()
    return jsonify({"recording": False})

@app.route("/api/record/status")
def api_record_status():
    """Return current recording state."""
    if _udp_listener.is_recording:
        return jsonify({"recording": True, "game": "f1", "path": _udp_listener.recording_path})
    if _lmu_listener.is_recording:
        return jsonify({"recording": True, "game": "lmu", "path": _lmu_listener.recording_path})
    return jsonify({"recording": False})

@app.route("/telemetry")
def telemetry():
    return render_template("telemetry.html")

@app.route("/strategy")
def strategy():
    return render_template("strategy.html")



#---------- SETTINGS / SETUP ----------#

@app.route("/setup")
def setup():
    return render_template("setup.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5051))
    # use_reloader=False: Flask's reloader forks the process, which would create
    # duplicate UDP/TCP listener threads. threaded=True handles concurrent SSE clients.
    app.run(debug=True, use_reloader=False, threaded=True, host="0.0.0.0", port=port)
