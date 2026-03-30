# Le Mans Ultimate — Connection FAQ

Common issues when connecting SimStrategist to Le Mans Ultimate via the
**Ultimate Telemetry Socket – JSON Telemetry Plugin**, and how to fix them.

---

## 1. No telemetry data appears / dashboard stays blank

**Cause:** The server is not receiving any packets from LMU.

**Fixes:**
- Confirm the JSON Telemetry Plugin is installed and **enabled** in LMU's plugin manager.
- Make sure you are actually in a session (practice, qualifying, or race). The plugin only sends data while driving.
- Check that the plugin is configured to send to `127.0.0.1:5000` (TCP) or the same host/port you passed with `--host` / `--port`.
- Run the server with verbose logging and watch for the "Plugin connected" log line:
  ```
  python3 -m lmu.server
  ```
  If you never see `Plugin connected from 127.0.0.1:...`, the plugin is not reaching the server.

---

## 2. `ConnectionRefusedError` or "address already in use"

**Cause:** Either the server is not running, or another process is already bound to port 5000.

**Fixes:**
- Make sure `python3 -m lmu.server` (or `app.py`) is running **before** LMU tries to connect.
- Find and kill the conflicting process:
  ```bash
  # Linux / macOS
  lsof -i :5000
  kill <PID>

  # Windows
  netstat -ano | findstr :5000
  taskkill /PID <PID> /F
  ```
- Or start the server on a different port and update the plugin to match:
  ```bash
  python3 -m lmu.server --port 5101
  ```

---

## 3. Plugin connects but data stops updating after a few seconds

**Cause:** The connection is marked stale. `STALE_TIMEOUT` (default 2 s) expires when no packets arrive.

**Fixes:**
- If you paused or alt-tabbed mid-session, data will resume once you return to driving.
- If the game is running but data genuinely stops, the plugin may have disconnected silently. Restart `lmu.server`; the plugin will reconnect on the next session.
- Increase `STALE_TIMEOUT` in [config.py](config.py) if your rig has high frame-time variance:
  ```python
  STALE_TIMEOUT = 5.0
  ```

---

## 4. JSON parse errors in the log

**Cause:** The plugin sent a malformed or incomplete JSON document. Most common in UDP mode when a large packet is fragmented.

**Fixes:**
- Switch to **TCP mode** (the default). TCP is a stream protocol, so the server reads complete newline-delimited documents and is not affected by datagram fragmentation:
  ```bash
  python3 -m lmu.server        # TCP (recommended)
  python3 -m lmu.server --udp  # UDP (use only if TCP unavailable)
  ```
- If you must use UDP, ensure the plugin sends compact JSON (no extra whitespace) to keep datagrams below the 65 535-byte `BUFSIZE`.

---

## 5. Speed / RPM values look wrong (e.g. speed reads ~0.08 instead of 300)

**Cause:** Unit mismatch. The plugin sends speed in **m/s**; the dashboard converts to km/h using `SPEED_MS_TO_KPH = 3.6`.

**Fixes:**
- Confirm the plugin is sending SI units. Some community builds send km/h directly. If so, set in [config.py](config.py):
  ```python
  SPEED_MS_TO_KPH = 1.0
  ```
- RPM is capped by `RPM_MAX_ESTIMATE = 12000` for the rev-light display. Adjust this for cars with a higher rev ceiling:
  ```python
  RPM_MAX_ESTIMATE = 15000
  ```

---

## 6. Missing fields (fuel, temperatures, steering, etc.)

**Cause:** Some plugin builds omit optional fields or use different key names.

**Details:** The server handles several alternate key names automatically (e.g. `engineRpm` vs `rpm`, `steer` vs `steering`, and multiple `vehicleClass` aliases). Fields listed in `OPTIONAL_TELEMETRY_FIELDS` are safe to be absent.

**Fix:** If a specific field you need is absent, check what key name the plugin actually sends by running:
```bash
python3 -m lmu.server  # then watch DEBUG log output
```
Enable debug-level logging first:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```
Then add a mapping for the new key in the `_dispatch()` function in [server.py](server.py).

---

## 7. Firewall blocking the connection (remote machine setup)

**Cause:** The server binds to `127.0.0.1` by default, which rejects connections from other machines.

**Fix:** Bind to all interfaces and open the port in your firewall:
```bash
python3 -m lmu.server --host 0.0.0.0 --port 5000
```
Then configure the LMU plugin to send to your machine's LAN IP instead of `127.0.0.1`.

> **Note:** Only do this on a trusted local network. Do not expose port 5000 to the public internet.

---

## 8. Server crashes immediately on startup

**Common causes and fixes:**

| Error | Fix |
|---|---|
| `ModuleNotFoundError: lmu.telemetry_state` | Run from the project root: `python3 -m lmu.server` (not `python3 lmu/server.py`) |
| `PermissionError: [Errno 13]` on port 5000 | Use a port above 1024; ports ≤ 1024 require root on Linux/macOS |
| `OSError: [Errno 98] Address already in use` | See issue #2 above |

---

## 9. Dashboard works in TCP mode but the plugin only supports UDP

**Fix:** Pass `--udp` when starting the server:
```bash
python3 -m lmu.server --udp --port 5000
```
Ensure the plugin's destination port matches. Note the caveats around fragmentation in issue #4.
