"""
LMU Telemetry Replayer
Reads a .lmurec file and sends JSON documents to the LMU TCP listener,
reproducing the original timing so the live server processes them normally.

Usage:
    # Start app.py (or lmu/server.py) first, then replay:
    python3 lmu/replayer.py example-data/lmu_session.lmurec
    python3 lmu/replayer.py example-data/lmu_session.lmurec --speed 2.0
    python3 lmu/replayer.py example-data/lmu_session.lmurec --loop
    python3 lmu/replayer.py example-data/lmu_session.lmurec --speed 0 --loop  # max speed

File format expected (produced by recorder.py):
    Header (16 bytes):
        b'LMUREC'  - 6-byte magic
        uint8      - version (must be 1)
        9 bytes    - reserved/padding

    Per-record:
        float64    - timestamp (seconds since recording started)
        uint16     - record length in bytes
        bytes      - raw JSON bytes (without trailing newline)
"""
import argparse
import logging
import socket
import struct
import sys
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('LMUReplayer')

MAGIC = b'LMUREC'
HEADER_SIZE = 16
RECORD_HEADER_FMT = '<dH'
RECORD_HEADER_SIZE = struct.calcsize(RECORD_HEADER_FMT)


def read_records(path: str):
    """Generator that yields (timestamp_seconds, raw_json_bytes) from a .lmurec file."""
    with open(path, 'rb') as f:
        header = f.read(HEADER_SIZE)
        if len(header) < HEADER_SIZE:
            raise ValueError(f"File too short to be a valid .lmurec file: {path!r}")
        if header[:6] != MAGIC:
            raise ValueError(f"Not a .lmurec file (bad magic bytes): {path!r}")
        if header[6] != 1:
            raise ValueError(f"Unsupported .lmurec version {header[6]} (expected 1)")

        while True:
            rec_header = f.read(RECORD_HEADER_SIZE)
            if not rec_header:
                return  # EOF
            if len(rec_header) < RECORD_HEADER_SIZE:
                logger.warning("Truncated record header at end of file — stopping")
                return
            timestamp, length = struct.unpack(RECORD_HEADER_FMT, rec_header)
            data = f.read(length)
            if len(data) < length:
                logger.warning("Truncated record data at end of file — stopping")
                return
            yield timestamp, data


def replay(path: str, host: str, port: int, speed: float, loop: bool):
    iteration = 0
    while True:
        iteration += 1
        if iteration > 1:
            logger.info(f"Looping replay (iteration {iteration})...")

        records = list(read_records(path))
        if not records:
            logger.error("No records found in recording — exiting")
            break

        total = len(records)
        logger.info(f"Replaying {total} records from {path!r} to {host}:{port} at {speed}x speed")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
        except ConnectionRefusedError:
            logger.error(f"Could not connect to {host}:{port} — is the LMU listener running?")
            sys.exit(1)

        wall_start = time.monotonic()
        rec_start = records[0][0]

        sent = 0
        try:
            for rec_ts, data in records:
                if speed > 0:
                    target_wall = wall_start + (rec_ts - rec_start) / speed
                    sleep_for = target_wall - time.monotonic()
                    if sleep_for > 0:
                        time.sleep(sleep_for)

                # Send JSON line with trailing newline (as the real plugin does)
                sock.sendall(data + b'\n')
                sent += 1

                if sent % 1000 == 0:
                    elapsed = time.monotonic() - wall_start
                    logger.info(f"Sent {sent}/{total} records ({elapsed:.1f}s elapsed)")

        finally:
            sock.close()

        elapsed = time.monotonic() - wall_start
        logger.info(f"Replay complete — {sent} records sent in {elapsed:.2f}s")

        if not loop:
            break


def main():
    parser = argparse.ArgumentParser(description='Replay a .lmurec recording to the LMU TCP server')
    parser.add_argument('input', help='Input .lmurec file (e.g. example-data/lmu_session.lmurec)')
    parser.add_argument('--host', default='127.0.0.1', help='TCP host to connect to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5100, help='TCP port to connect to (default: 5100)')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Playback speed multiplier (default: 1.0, use 0 for max speed)')
    parser.add_argument('--loop', action='store_true', help='Loop replay indefinitely')
    args = parser.parse_args()

    try:
        replay(args.input, args.host, args.port, args.speed, args.loop)
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Replay interrupted")


if __name__ == '__main__':
    main()
