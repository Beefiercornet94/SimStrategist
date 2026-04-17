"""
RaceRoom Racing Experience — Shared Memory Reader
Polls the $R3E Windows named shared memory region at POLL_HZ and pushes
parsed data into TelemetryState.

Protocol : Windows shared memory ($R3E), packed binary C struct, no network.
API ref  : https://github.com/sector3studios/r3e-api  (targets API v3.x)

Byte offsets below are analytically derived from R3E.cs (pack=1).
Layout summary (cumulative from offset 0):
  0   Header       16 B  (VersionMajor/Minor, AllDriversOffset, DriverDataSize)
  16  GameState    24 B  (6 × int32)
  40  PlayerData  536 B  (high-precision physics — skipped via padding)
  576 Session/Pit/Scoring/Flags/DriverInfo/VehicleState/TireData  …
  1880 NumCars     4 B
"""

import logging
import mmap
import struct
import sys
import threading
import time

from race_room.config import DISCONNECT_TIMEOUT, POLL_HZ
from race_room.telemetry_state import state

logger = logging.getLogger(__name__)

_SHMEM_NAME = '$R3E'
_MIN_READ   = 1884   # bytes needed to reach NumCars (offset 1880)
_API_VER    = 3      # VersionMajor this implementation targets

# ---------------------------------------------------------------------------
# Byte offsets into the R3E Shared struct (API v3.x, #pragma pack(1))
# ---------------------------------------------------------------------------
_O_VER_MAJOR  = 0
# -- session --
_O_TRACK      = 576   # char[64]  track name
_O_LAYOUT     = 640   # char[64]  layout name
_O_SES_TYPE   = 716   # int32    -1=unavail 0=Practice 1=Qualify 2=Race 3=Warmup
_O_SES_REMAIN = 764   # float32   seconds remaining in session
_O_IN_PIT     = 816   # int32     boolean — player in pitlane
# -- scoring --
_O_POSITION   = 900   # int32     race position (1-based)
_O_LAPS_DONE  = 912   # int32     completed laps
_O_LAP_BEST   = 940   # float32   personal best lap (s), -1 = none
_O_LAP_PREV   = 944   # float32   previous lap (s), -1 = none
_O_LAP_CUR    = 948   # float32   current ongoing lap (s)
# -- vehicle --
_O_GEAR       = 1272  # int32    -1=R 0=N 1+=forward gears
_O_SPEED      = 1292  # float32   m/s
_O_ENG_RPS    = 1296  # float32   rad/s  (× 9.549 → RPM)
_O_FUEL       = 1312  # float32   liters remaining
_O_FUEL_LAP   = 1320  # float32   liters/lap estimate
_O_ENG_TEMP   = 1336  # float32   °C
_O_THROTTLE   = 1356  # float32   0.0–1.0
_O_BRAKE      = 1364  # float32   0.0–1.0
_O_CLUTCH     = 1372  # float32   0.0–1.0
_O_STEER      = 1380  # float32  −1.0 to +1.0
# -- tires (FL FR RL RR) --
_O_TIRE_WEAR  = 1592  # 4 × float32   0.0–1.0
_O_TIRE_PRES  = 1608  # 4 × float32   kPa
# TireTempInformation[4]: each 24 B; CurrentTemp.Center is at +4 within each
_O_TIRE_TEMP  = 1704  # first of 4 × 24-byte TireTempInformation blocks
# -- misc --
_O_NUM_CARS   = 1880  # int32     total cars on track


def _parse(raw: bytes) -> dict | None:
    """Unpack a raw $R3E snapshot into a flat telemetry dict.  Returns None
    if the buffer is too short or the API major version doesn't match."""
    if len(raw) < _MIN_READ:
        return None
    if struct.unpack_from('<i', raw, _O_VER_MAJOR)[0] != _API_VER:
        return None

    track  = raw[_O_TRACK  : _O_TRACK  + 64].rstrip(b'\x00').decode('utf-8', errors='replace')
    layout = raw[_O_LAYOUT : _O_LAYOUT + 64].rstrip(b'\x00').decode('utf-8', errors='replace')

    u_i  = lambda off: struct.unpack_from('<i', raw, off)[0]
    u_f  = lambda off: struct.unpack_from('<f', raw, off)[0]
    u_4f = lambda off: list(struct.unpack_from('<4f', raw, off))

    lap_cur  = u_f(_O_LAP_CUR)
    lap_prev = u_f(_O_LAP_PREV)
    lap_best = u_f(_O_LAP_BEST)

    return {
        # telemetry
        'speed_kmh':      u_f(_O_SPEED) * 3.6,
        'rpm':            u_f(_O_ENG_RPS) * 9.549,
        'gear':           u_i(_O_GEAR),
        'throttle':       u_f(_O_THROTTLE),
        'brake':          u_f(_O_BRAKE),
        'clutch':         u_f(_O_CLUTCH),
        'steer':          u_f(_O_STEER),
        'fuel':           u_f(_O_FUEL),
        'fuel_per_lap':   u_f(_O_FUEL_LAP),
        'engine_temp':    u_f(_O_ENG_TEMP),
        'tyre_wear':      u_4f(_O_TIRE_WEAR),
        'tyre_pressure':  u_4f(_O_TIRE_PRES),
        # center tread temp per wheel; each TireTempInformation is 24 B, Center at +4
        'tyre_temp': [struct.unpack_from('<f', raw, _O_TIRE_TEMP + i * 24 + 4)[0]
                      for i in range(4)],
        # lap data
        'current_lap_time': max(lap_cur, 0.0),
        'last_lap_time':    max(lap_prev, 0.0),
        'best_lap_time':    max(lap_best, 0.0),
        'car_position':     u_i(_O_POSITION),
        'current_lap':      u_i(_O_LAPS_DONE),
        'pit_status':       u_i(_O_IN_PIT),
        # session
        'track_name':             track,
        'layout_name':            layout,
        'session_type':           u_i(_O_SES_TYPE),
        'session_time_remaining': u_f(_O_SES_REMAIN),
        'num_vehicles':           u_i(_O_NUM_CARS),
    }


class SharedMemoryReader(threading.Thread):
    """Polls $R3E shared memory at POLL_HZ and pushes data to TelemetryState.

    Windows-only: on any other platform the thread logs a warning and exits
    immediately, leaving the rest of the app unaffected.
    """

    def __init__(self):
        super().__init__(daemon=True, name='R3ESharedMemoryReader')
        self.running = False

    def run(self) -> None:
        if sys.platform != 'win32':
            logger.warning('RaceRoom shared memory requires Windows; listener idle.')
            return

        self.running = True
        interval = 1.0 / POLL_HZ
        logger.info('RaceRoom shared memory reader started at %d Hz', POLL_HZ)

        shm = None
        while self.running:
            try:
                if shm is None:
                    shm = mmap.mmap(-1, _MIN_READ, tagname=_SHMEM_NAME,
                                    access=mmap.ACCESS_READ)
                shm.seek(0)
                parsed = _parse(shm.read(_MIN_READ))
                if parsed:
                    state.update(parsed)
            except OSError:
                # Game not running yet; close stale handle and retry next tick
                if shm:
                    shm.close()
                    shm = None
            except Exception as exc:
                logger.debug('R3E read error: %s', exc)
            time.sleep(interval)

        if shm:
            shm.close()
        logger.info('RaceRoom shared memory reader stopped.')

    def stop(self) -> None:
        self.running = False
