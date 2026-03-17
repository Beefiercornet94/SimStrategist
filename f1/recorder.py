"""
F1 Telemetry Recorder
Listens on UDP port 20777 and saves raw packets to a .f1rec binary file.

Usage:
    python3 f1/recorder.py example-data/mysession.f1rec
    python3 f1/recorder.py example-data/mysession.f1rec --port 20777

File format:
    Header (16 bytes):
        b'F1REC\x00'  - 6-byte magic
        uint8         - version (1)
        9 bytes       - reserved/padding

    Per-packet record:
        float64       - timestamp (seconds since recording started)
        uint16        - packet length in bytes
        bytes         - raw packet data
"""
import argparse
import logging
import os
import socket
import struct
import sys
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('F1Recorder')

MAGIC = b'F1REC\x00'
VERSION = 1
HEADER_SIZE = 16  # 6 magic + 1 version + 9 reserved
RECORD_HEADER_FMT = '<dH'  # float64 timestamp + uint16 length
RECORD_HEADER_SIZE = struct.calcsize(RECORD_HEADER_FMT)


def write_file_header(f):
    header = MAGIC + bytes([VERSION]) + b'\x00' * 9
    f.write(header)


def record(output_path: str, udp_port: int, buffer_size: int = 2048):
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', udp_port))
    logger.info(f"Listening on UDP port {udp_port}, recording to {output_path!r}")

    packet_count = 0
    start_time = None

    with open(output_path, 'wb') as f:
        write_file_header(f)
        try:
            while True:
                data, addr = sock.recvfrom(buffer_size)
                now = time.monotonic()
                if start_time is None:
                    start_time = now
                    logger.info("First packet received — recording started")
                elapsed = now - start_time

                record_header = struct.pack(RECORD_HEADER_FMT, elapsed, len(data))
                f.write(record_header)
                f.write(data)

                packet_count += 1
                if packet_count % 500 == 0:
                    f.flush()
                    logger.info(f"Recorded {packet_count} packets ({elapsed:.1f}s elapsed)")

        except KeyboardInterrupt:
            logger.info(f"Recording stopped — {packet_count} packets saved to {output_path!r}")
        finally:
            sock.close()


def main():
    parser = argparse.ArgumentParser(description='Record F1 UDP telemetry to a .f1rec file')
    parser.add_argument('output', help='Output file path (e.g. example-data/session.f1rec)')
    parser.add_argument('--port', type=int, default=20777, help='UDP port to listen on (default: 20777)')
    parser.add_argument('--buffer', type=int, default=2048, help='UDP buffer size in bytes (default: 2048)')
    args = parser.parse_args()

    record(args.output, args.port, args.buffer)


if __name__ == '__main__':
    main()
