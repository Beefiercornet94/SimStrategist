"""
LMU Telemetry Recorder
Listens for TCP connections from the Le Mans Ultimate JSON Telemetry Plugin
and saves each JSON document to a .lmurec binary file.

Usage:
    python3 lmu/recorder.py example-data/lmu_session.lmurec
    python3 lmu/recorder.py example-data/lmu_session.lmurec --port 5100

File format:
    Header (16 bytes):
        b'LMUREC'  - 6-byte magic
        uint8      - version (1)
        9 bytes    - reserved/padding

    Per-record:
        float64    - timestamp (seconds since recording started)
        uint16     - record length in bytes
        bytes      - raw JSON bytes (without trailing newline)
"""
import argparse
import logging
import os
import socket
import struct
import sys
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('LMURecorder')

MAGIC = b'LMUREC'
VERSION = 1
HEADER_SIZE = 16  # 6 magic + 1 version + 9 reserved
RECORD_HEADER_FMT = '<dH'  # float64 timestamp + uint16 length
RECORD_HEADER_SIZE = struct.calcsize(RECORD_HEADER_FMT)


def write_file_header(f):
    header = MAGIC + bytes([VERSION]) + b'\x00' * 9
    f.write(header)


def record(output_path: str, host: str, port: int):
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(1)
    logger.info(f"Waiting for plugin connection on {host}:{port}, recording to {output_path!r}")

    record_count = 0
    start_time = None

    try:
        conn, addr = server_sock.accept()
        logger.info(f"Plugin connected from {addr[0]}:{addr[1]} — recording started")

        with open(output_path, 'wb') as f, conn, conn.makefile('rb') as stream:
            write_file_header(f)
            try:
                for raw_line in stream:
                    data = raw_line.strip()
                    if not data:
                        continue

                    now = time.monotonic()
                    if start_time is None:
                        start_time = now
                    elapsed = now - start_time

                    record_header = struct.pack(RECORD_HEADER_FMT, elapsed, len(data))
                    f.write(record_header)
                    f.write(data)

                    record_count += 1
                    if record_count % 500 == 0:
                        f.flush()
                        logger.info(f"Recorded {record_count} documents ({elapsed:.1f}s elapsed)")

            except KeyboardInterrupt:
                pass

        logger.info(f"Recording stopped — {record_count} documents saved to {output_path!r}")

    except KeyboardInterrupt:
        logger.info("Interrupted before plugin connected")
    finally:
        server_sock.close()


def main():
    parser = argparse.ArgumentParser(description='Record LMU JSON telemetry to a .lmurec file')
    parser.add_argument('output', help='Output file path (e.g. example-data/lmu_session.lmurec)')
    parser.add_argument('--host', default='127.0.0.1', help='Bind address (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5100, help='TCP port to listen on (default: 5100)')
    args = parser.parse_args()

    record(args.output, args.host, args.port)


if __name__ == '__main__':
    main()
