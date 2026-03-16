#---------- SETUP / CONFIG ----------#

# Import requirements
import json
import os
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


# Configure application
app = Flask(__name__)

# Start F1 UDP listener as background daemon thread
_udp_listener = UdpListener()
_udp_listener.start()

# Start LMU TCP listener as background daemon thread
_lmu_listener = LmuTcpListener()
_lmu_listener.start()

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
    response.headers["Expires"] = 0
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
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Must provide username", 400)

        # Ensures username is unique
        count = int(db.execute("SELECT COUNT(username) FROM users")[0]["COUNT(username)"])
        taken_names = db.execute("SELECT username FROM users")
        for i in range(count):
            if request.form.get("username") == taken_names[i]["username"]:
                return apology("Username taken :(", 400)

        # Ensure password was submitted
        if not request.form.get("password") or not request.form.get("confirmation"):
            return apology("Must provide password", 400)
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords must match", 400)

        # Creates account
        username = request.form.get("username")
        password = generate_password_hash(request.form.get("password"))
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?);", username, password)
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
                last_seen = updated
                payload = json.dumps(src.get_snapshot())
                yield f"data: {payload}\n\n"
            else:
                # Keepalive comment so the connection stays open
                yield ": keepalive\n\n"
            time.sleep(0.016)   # ~60 Hz check rate → ≤16 ms latency

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )

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
    if request.method == "GET":
        return render_template("setup.html")
    
    elif request.method == "POST":
        return redirect("/")

    else:
        return apology("We f**ked up :/", 500)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, threaded=True)