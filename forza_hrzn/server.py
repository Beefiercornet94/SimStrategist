"""
Forza Horizon UDP Listener
Handles receiving and parsing binary UDP packets from Forza Horizon 4/5.

Game version is detected from packet size (no version field in packet):
  324 bytes → Forza Horizon 4
  323 bytes → Forza Horizon 5

Packet structure:
  Bytes 0–231  : Sled block (shared with all Forza titles)
  Bytes 232–310: Dash block (shared with Forza Motorsport 7)
  Bytes 311+   : Horizon extension (FH4: 13 bytes, FH5: 12 bytes)
"""

import logging
import socket
import struct
import threading

from forza_hrzn.config import (
    BUFFER_SIZE,
    FH5_PORT,
    UDP_IP,
    VERSION_BY_SIZE,
)
from forza_hrzn.telemetry_state import state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ForzaHorizonUDP')

# ---------------------------------------------------------------------------
# Struct format for the shared Sled + Dash blocks (bytes 0–310, 311 bytes).
#
# Block 1 — Sled (bytes 0–231):
#   iI       IsRaceOn, TimestampMs
#   fff      MaxRPM, IdleRPM, CurrentEngineRpm
#   fff      AccelerationX/Y/Z
#   fff      VelocityX/Y/Z
#   fff      AngularVelocityX/Y/Z
#   fff      Yaw, Pitch, Roll
#   ffff×9   SuspTravel, SlipRatio, WheelSpeed, WheelRumble,
#            PuddleDepth, SurfRumble, SlipAngle, CombinedSlip,
#            SuspTravelMeters  (each ×4 wheels)
#   iiiii    CarOrdinal, CarClass, CarPerfIndex, DriveTrain, NumCylinders
#
# Block 2 — Dash (bytes 232–310):
#   fff      PositionX/Y/Z
#   fff      Speed (m/s), Power (W), Torque (Nm)
#   ffff     TireTemp FL/FR/RL/RR (°C)
#   fffffff  Boost, Fuel, DistanceTraveled, BestLap, LastLap,
#            CurrentLap, CurrentRaceTime
#   H        LapNumber
#   BBBBBB   RacePosition, Accel, Brake, Clutch, HandBrake, Gear
#   bbb      Steer, NormDrivingLine, NormAIBrakeDiff
# ---------------------------------------------------------------------------
_SLED_DASH_FMT = (
    '<'
    'iI'          # IsRaceOn, TimestampMs
    'fff'         # MaxRPM, IdleRPM, CurrentEngineRpm
    'fff'         # AccX/Y/Z
    'fff'         # VelX/Y/Z
    'fff'         # AngVelX/Y/Z
    'fff'         # Yaw, Pitch, Roll
    'ffff'        # NormSuspTravel ×4
    'ffff'        # TireSlipRatio ×4
    'ffff'        # WheelRotationSpeed ×4
    'ffff'        # WheelOnRumbleStrip ×4
    'ffff'        # WheelInPuddleDepth ×4
    'ffff'        # SurfaceRumble ×4
    'ffff'        # TireSlipAngle ×4
    'ffff'        # TireCombinedSlip ×4
    'ffff'        # SuspensionTravelMeters ×4
    'iiiii'       # CarOrdinal, CarClass, CarPerfIndex, DriveTrain, NumCylinders
    'fff'         # PositionX/Y/Z
    'fff'         # Speed, Power, Torque
    'ffff'        # TireTemp ×4
    'fffffff'     # Boost, Fuel, DistanceTraveled, BestLap, LastLap, CurrentLap, CurrentRaceTime
    'H'           # LapNumber
    'BBBBBB'      # RacePosition, Accel, Brake, Clutch, HandBrake, Gear
    'bbb'         # Steer, NormDrivingLine, NormAIBrakeDiff
)
_SLED_DASH_SIZE = struct.calcsize(_SLED_DASH_FMT)  # must equal 311

# Field index constants (0-based indices into the unpacked tuple)
_IDX_IS_RACE_ON     = 0
_IDX_MAX_RPM        = 2
_IDX_CURRENT_RPM    = 4
_IDX_CAR_CLASS      = 54
_IDX_CAR_PERF_INDEX = 55
_IDX_SPEED          = 61
_IDX_TIRE_TEMP_FL   = 64
_IDX_BOOST          = 68
_IDX_FUEL           = 69
_IDX_BEST_LAP       = 71
_IDX_LAST_LAP       = 72
_IDX_CURRENT_LAP    = 73
_IDX_LAP_NUMBER     = 75
_IDX_RACE_POSITION  = 76
_IDX_ACCEL          = 77
_IDX_BRAKE          = 78
_IDX_CLUTCH         = 79
_IDX_GEAR           = 81
_IDX_STEER          = 82


def _parse(packet: bytes, version: str) -> dict | None:
    """Parse a Forza Horizon UDP packet into a telemetry dict."""
    if len(packet) < _SLED_DASH_SIZE:
        return None
    try:
        d = struct.unpack_from(_SLED_DASH_FMT, packet)
    except struct.error:
        return None

    return {
        'is_race_on':     d[_IDX_IS_RACE_ON],
        'rpm':            d[_IDX_CURRENT_RPM],
        'max_rpm':        d[_IDX_MAX_RPM],
        'speed_kmh':      d[_IDX_SPEED] * 3.6,
        'gear':           d[_IDX_GEAR],          # 0=R, 1=N, 2–9 = gears 1–8
        'throttle':       d[_IDX_ACCEL] / 255.0,
        'brake':          d[_IDX_BRAKE] / 255.0,
        'clutch':         d[_IDX_CLUTCH] / 255.0,
        'steer':          d[_IDX_STEER] / 127.0,
        'tyre_temp':      [d[_IDX_TIRE_TEMP_FL + i] for i in range(4)],
        'fuel':           d[_IDX_FUEL],
        'boost':          d[_IDX_BOOST],
        'car_class':      d[_IDX_CAR_CLASS],
        'car_perf_index': d[_IDX_CAR_PERF_INDEX],
        'lap_number':     d[_IDX_LAP_NUMBER],
        'current_lap':    d[_IDX_CURRENT_LAP],
        'last_lap':       d[_IDX_LAST_LAP],
        'best_lap':       d[_IDX_BEST_LAP],
        'race_position':  d[_IDX_RACE_POSITION],
    }


class UdpListener(threading.Thread):
    """Listens on a single UDP port and routes packets to telemetry_state."""

    def __init__(self, port: int = FH5_PORT):
        super().__init__()
        self.port = port
        self.daemon = True
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running = False

    def run(self) -> None:
        self.running = True
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((UDP_IP, self.port))
        logger.info(f'Forza Horizon UDP listener started on port {self.port}')

        while self.running:
            try:
                data, _ = self._sock.recvfrom(BUFFER_SIZE)
            except OSError:
                break

            version = VERSION_BY_SIZE.get(len(data))
            if version is None:
                logger.debug(
                    f'Unexpected packet size {len(data)} — not a supported Forza Horizon packet'
                )
                continue

            parsed = _parse(data, version)
            if parsed is None:
                continue

            state.game_version = version
            state.update(parsed)

        logger.info('Forza Horizon UDP listener stopped')
        self._sock.close()

    def stop(self) -> None:
        self.running = False
        self._sock.close()
