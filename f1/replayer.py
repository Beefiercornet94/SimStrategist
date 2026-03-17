"""
F1 Telemetry Replayer
Reads a .f1rec binary file and sends packets to the local UDP port,
reproducing the original timing so the live server processes them normally.

Usage:
    # Start the server first, then replay:
    python3 f1/replayer.py example-data/session.f1rec
    python3 f1/replayer.py example-data/session.f1rec --speed 2.0
    python3 f1/replayer.py example-data/session.f1rec --loop
    python3 f1/replayer.py example-data/session.f1rec --speed 0 --loop  # send as fast as possible

File format expected (produced by recorder.py):
    Header (16 bytes):
        b'F1REC\x00'  - 6-byte magic
        uint8         - version (must be 1)
        9 bytes       - reserved/padding

    Per-packet record:
        float64       - timestamp (seconds since recording started)
        uint16        - packet length in bytes
        bytes         - raw packet data
"""
import argparse
import logging
import socket
import struct
import sys
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('F1Replayer')

MAGIC = b'F1REC\x00'
HEADER_SIZE = 16
RECORD_HEADER_FMT = '<dH'
RECORD_HEADER_SIZE = struct.calcsize(RECORD_HEADER_FMT)


def read_packets(path: str):
    """Generator that yields (timestamp_seconds, raw_data) tuples from a .f1rec file."""
    with open(path, 'rb') as f:
        header = f.read(HEADER_SIZE)
        if len(header) < HEADER_SIZE:
            raise ValueError(f"File too short to be a valid .f1rec file: {path!r}")
        magic = header[:6]
        version = header[6]
        if magic != MAGIC:
            raise ValueError(f"Not a .f1rec file (bad magic bytes): {path!r}")
        if version != 1:
            raise ValueError(f"Unsupported .f1rec version {version} (expected 1)")

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
                logger.warning("Truncated packet data at end of file — stopping")
                return
            yield timestamp, data


def replay(path: str, host: str, port: int, speed: float, loop: bool):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target = (host, port)

    iteration = 0
    while True:
        iteration += 1
        if iteration > 1:
            logger.info(f"Looping replay (iteration {iteration})...")

        packets = list(read_packets(path))
        if not packets:
            logger.error("No packets found in recording — exiting")
            break

        total = len(packets)
        logger.info(f"Replaying {total} packets from {path!r} to {host}:{port} at {speed}x speed")

        wall_start = time.monotonic()
        rec_start = packets[0][0]  # first packet timestamp (usually 0.0)

        sent = 0
        for rec_ts, data in packets:
            if speed > 0:
                # Calculate when this packet should be sent relative to wall_start
                target_wall = wall_start + (rec_ts - rec_start) / speed
                sleep_for = target_wall - time.monotonic()
                if sleep_for > 0:
                    time.sleep(sleep_for)

            sock.sendto(data, target)
            sent += 1

            if sent % 1000 == 0:
                elapsed = time.monotonic() - wall_start
                logger.info(f"Sent {sent}/{total} packets ({elapsed:.1f}s elapsed)")

        elapsed = time.monotonic() - wall_start
        logger.info(f"Replay complete — {sent} packets sent in {elapsed:.2f}s")

        if not loop:
            break

    sock.close()


def main():
    parser = argparse.ArgumentParser(description='Replay a .f1rec telemetry recording to the F1 UDP server')
    parser.add_argument('input', help='Input .f1rec file (e.g. example-data/session.f1rec)')
    parser.add_argument('--host', default='127.0.0.1', help='UDP host to send to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=20777, help='UDP port to send to (default: 20777)')
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
