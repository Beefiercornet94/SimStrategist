#---------- SETUP / CONFIG ----------#

# Import requirements
import json
import os
import threading
import time
from cs50 import SQL
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session, stream_with_context
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required

from f1.server import UdpListener
from f1.telemetry_state import state as f1_state

from lmu.server import TcpListener as LmuTcpListener
from lmu.telemetry_state import state as lmu_state

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



#---------- LOGIN / LOGOUT / REGISTER ----------#
"""FROM CS50x's FINANCE PROBLEM SET"""

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/setup")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id & return to start
    session.clear()
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "GET":
        return render_template("register.html")

    elif request.method == "POST":
        username     = request.form.get("username", "")
        password     = request.form.get("password", "")
        confirmation = request.form.get("confirmation", "")

        # Ensure username was submitted
        if not username:
            return apology("Must provide username", 400)

        # Ensures username is unique
        count = int(db.execute("SELECT COUNT(username) FROM users")[0]["COUNT(username)"])
        taken_names = db.execute("SELECT username FROM users")
        for i in range(count):
            if username == taken_names[i]["username"]:
                return apology("Username taken :(", 400)

        # Ensure password was submitted
        if not password or not confirmation:
            return apology("Must provide password", 400)
        if password != confirmation:
            return apology("Passwords must match", 400)

        # Creates account
        password = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, password)
        return redirect("/")

    else:
        return apology("We f**ked up :/", 500)



#---------- INDEX ----------#

@app.route("/")
def index():
    return render_template("index.html")



#---------- TELEMETRY / STRATEGY ----------#

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
    src  = lmu_state if game == "lmu" else f1_state

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

@app.route("/telemetry")
def telemetry():
    return render_template("telemetry.html")

@app.route("/strategy")
def strategy():
    return render_template("strategy.html")


#---------- SETTINGS / SETUP ----------#

@app.route("/setup", methods=["GET", "POST"])
@login_required
def setup():
        return render_template("setup.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5051))
    # use_reloader=False: Flask's reloader forks the process, which would create
    # duplicate UDP/TCP listener threads. threaded=True handles concurrent SSE clients.
    app.run(debug=True, use_reloader=False, threaded=True, host="0.0.0.0", port=port)
