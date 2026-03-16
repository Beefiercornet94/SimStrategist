"""
LMU JSON Telemetry Listener
Receives JSON telemetry from the Le Mans Ultimate
"Ultimate Telemetry Socket – JSON Telemetry Plugin".

Supports both TCP (streaming) and UDP (datagram) modes.
Default: TCP server on 127.0.0.1:5000.

The plugin sends a JSON object per update.  TCP mode expects each
JSON document to be terminated by a newline ('\\n').  UDP mode
treats each datagram as one complete JSON document.

Run standalone:
    python3 -m lmu.server              # TCP (default)
    python3 -m lmu.server --udp        # UDP
    python3 -m lmu.server --port 5001  # custom port
"""

import argparse
import json
import logging
import socket
import threading
from typing import Dict, Any

from lmu.telemetry_state import state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('LMUJSON')

HOST    = '127.0.0.1'
PORT    = 5100
BUFSIZE = 65535   # max UDP datagram; TCP uses readline


# ---------------------------------------------------------------------------
# JSON → state dispatcher
# ---------------------------------------------------------------------------

def _dispatch(doc: Dict[str, Any]) -> None:
    """
    Map the plugin's JSON structure onto our telemetry state.

    The JSON Telemetry Plugin uses nested keys.  We normalise them here
    so the rest of the app sees a consistent dictionary shape.

    Expected top-level keys (all optional – we guard with .get()):
        vehicle  – per-car physics data
        lap      – lap / sector timing
        session  – track / session info
    """
    vehicle = doc.get('vehicle', doc)   # some builds flatten the object

    telemetry = {}
    if 'speed' in vehicle:
        telemetry['speed'] = float(vehicle['speed'])
    if 'engineRpm' in vehicle:
        telemetry['rpm'] = int(vehicle['engineRpm'])
    elif 'rpm' in vehicle:
        telemetry['rpm'] = int(vehicle['rpm'])
    if 'gear' in vehicle:
        telemetry['gear'] = int(vehicle['gear'])
    if 'throttle' in vehicle:
        telemetry['throttle'] = float(vehicle['throttle'])
    if 'brake' in vehicle:
        telemetry['brake'] = float(vehicle['brake'])
    if 'clutch' in vehicle:
        telemetry['clutch'] = float(vehicle['clutch'])
    if 'steer' in vehicle or 'steering' in vehicle:
        telemetry['steer'] = float(vehicle.get('steer', vehicle.get('steering', 0)))
    if 'fuel' in vehicle:
        telemetry['fuel'] = float(vehicle['fuel'])
    if 'engineWaterTemp' in vehicle:
        telemetry['engine_water_temp'] = float(vehicle['engineWaterTemp'])
    if 'engineOilTemp' in vehicle:
        telemetry['engine_oil_temp'] = float(vehicle['engineOilTemp'])

    if telemetry:
        state.update_telemetry(telemetry)

    lap_raw = doc.get('lap', {})
    lap = {}
    if 'currentLapTime' in lap_raw:
        lap['current_lap_time'] = float(lap_raw['currentLapTime'])
    if 'lastLapTime' in lap_raw:
        lap['last_lap_time'] = float(lap_raw['lastLapTime'])
    if 'bestLapTime' in lap_raw:
        lap['best_lap_time'] = float(lap_raw['bestLapTime'])
    if 'sector1Time' in lap_raw:
        lap['sector1_time'] = float(lap_raw['sector1Time'])
    if 'sector2Time' in lap_raw:
        lap['sector2_time'] = float(lap_raw['sector2Time'])
    if 'lapNumber' in lap_raw:
        lap['current_lap'] = int(lap_raw['lapNumber'])
    if 'position' in lap_raw:
        lap['car_position'] = int(lap_raw['position'])
    if 'inPit' in lap_raw:
        lap['pit_status'] = int(lap_raw['inPit'])

    if lap:
        state.update_lap_data(lap)

    session_raw = doc.get('session', {})
    session = {}
    if 'trackName' in session_raw:
        session['track_name'] = session_raw['trackName']
    if 'sessionType' in session_raw:
        session['session_type'] = session_raw['sessionType']
    if 'flag' in session_raw:
        session['flag'] = session_raw['flag']
    if 'ambientTemp' in session_raw:
        session['ambient_temp'] = float(session_raw['ambientTemp'])
    if 'trackTemp' in session_raw:
        session['track_temp'] = float(session_raw['trackTemp'])
    if 'numVehicles' in session_raw:
        session['num_vehicles'] = int(session_raw['numVehicles'])

    if session:
        state.update_session(session)


def _parse_and_dispatch(raw: bytes) -> None:
    """Decode bytes, parse JSON, and dispatch."""
    text = raw.decode('utf-8', errors='replace').strip()
    if not text:
        return
    try:
        doc = json.loads(text)
        _dispatch(doc)
        logger.debug("Dispatched: speed=%.1f rpm=%d gear=%d",
                     state.telemetry.get('speed', 0) * 3.6,
                     state.telemetry.get('rpm', 0),
                     state.telemetry.get('gear', 0))
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse error: %s | raw=%r", exc, text[:120])


# ---------------------------------------------------------------------------
# TCP listener
# ---------------------------------------------------------------------------

class TcpListener(threading.Thread):
    """
    TCP server that accepts one persistent connection from the plugin.
    Reads newline-delimited JSON documents from the stream.
    """

    def __init__(self, host: str = HOST, port: int = PORT) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.running = False
        self._server_sock: socket.socket | None = None

    def run(self) -> None:
        self.running = True
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(1)
        logger.info("TCP listener ready on %s:%d", self.host, self.port)

        while self.running:
            try:
                self._server_sock.settimeout(1.0)
                try:
                    conn, addr = self._server_sock.accept()
                except socket.timeout:
                    continue

                logger.info("Plugin connected from %s:%d", *addr)
                self._handle_connection(conn)
            except Exception as exc:
                if self.running:
                    logger.error("TCP accept error: %s", exc)

        self._server_sock.close()
        logger.info("TCP listener stopped.")

    def _handle_connection(self, conn: socket.socket) -> None:
        try:
            with conn, conn.makefile('rb') as stream:
                for raw_line in stream:
                    if not self.running:
                        break
                    _parse_and_dispatch(raw_line)
        except Exception as exc:
            logger.warning("Connection error: %s", exc)
        finally:
            logger.info("Plugin disconnected.")

    def stop(self) -> None:
        self.running = False


# ---------------------------------------------------------------------------
# UDP listener
# ---------------------------------------------------------------------------

class UdpListener(threading.Thread):
    """
    UDP listener – each datagram is expected to be one complete JSON document.
    """

    def __init__(self, host: str = HOST, port: int = PORT) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.running = False
        self._sock: socket.socket | None = None

    def run(self) -> None:
        self.running = True
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.settimeout(1.0)
        logger.info("UDP listener ready on %s:%d", self.host, self.port)

        while self.running:
            try:
                data, _ = self._sock.recvfrom(BUFSIZE)
                _parse_and_dispatch(data)
            except socket.timeout:
                continue
            except Exception as exc:
                if self.running:
                    logger.error("UDP receive error: %s", exc)

        self._sock.close()
        logger.info("UDP listener stopped.")

    def stop(self) -> None:
        self.running = False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='LMU JSON Telemetry Listener')
    parser.add_argument('--udp',  action='store_true', help='Use UDP instead of TCP')
    parser.add_argument('--host', default=HOST,        help=f'Bind address (default: {HOST})')
    parser.add_argument('--port', default=PORT, type=int, help=f'Port (default: {PORT})')
    args = parser.parse_args()

    if args.udp:
        listener = UdpListener(host=args.host, port=args.port)
    else:
        listener = TcpListener(host=args.host, port=args.port)

    listener.start()
    logger.info("Press Ctrl+C to stop.")

    try:
        listener.join()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        listener.stop()
        listener.join(timeout=2)
