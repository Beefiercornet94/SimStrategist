# RaceRoom Racing Experience — SimStrategist Integration Plan

## Overview

This document describes how to add telemetry support for **RaceRoom Racing Experience (R3E)** to SimStrategist, following the same modular pattern used for F1, Le Mans Ultimate (LMU), and Forza Horizon.

---

## How RaceRoom Exports Telemetry

### Protocol: Windows Shared Memory

R3E uses **Windows Shared Memory (memory-mapped files)** — not UDP, TCP, or a named pipe. The game process (`RRRE.exe` or `RRRE64.exe`) creates a shared memory region named `$R3E` that any process on the same machine can open and read directly via OS APIs.

This is a **read-only, pull-based** interface. External applications poll it at whatever rate they choose (the physics sim updates at ~400 Hz, memory updates at ~512 Hz; polling at 60 Hz is more than sufficient for a dashboard).

**Key implications vs. existing implementations:**

| | F1 | LMU | Forza Horizon | RaceRoom |
|---|---|---|---|---|
| Transport | UDP socket (port 20777) | TCP socket (port 5100) | UDP socket (port 20055) | Windows shared memory (`$R3E`) |
| Data format | Binary struct (struct.unpack) | JSON (newline-delimited) | Binary struct (struct.unpack) | Binary struct (ctypes / mmap) |
| Network required | Yes (same LAN) | Yes (loopback) | Yes (same LAN) | No — same machine only |
| Python access | `socket` module | `socket` module | `socket` module | `mmap` + `ctypes` modules |
| Platform | Cross-platform | Cross-platform | Cross-platform | **Windows only** |

Because this is shared memory rather than a socket, the listener class needs to open the memory-mapped region by name, read a snapshot at each poll interval, and then parse the raw bytes — instead of blocking on `recvfrom()`.

### Data Format

The memory region holds a single large **packed binary C struct** (`#pragma pack(1)` — no alignment padding). The canonical definition is published by Sector3 Studios at [github.com/sector3studios/r3e-api](https://github.com/sector3studios/r3e-api):

- `r3e.h` — C header
- `R3E.cs` — C# struct (most complete and up-to-date reference)

The struct begins with a version header (`VersionMajor`, `VersionMinor`) that must be verified at startup. The current API version is **Major 3, Minor 5**. The header also contains `AllDriversOffset` and `DriverDataSize` fields pointing to the variable-length competitor array (up to 128 drivers) at the end of the struct.

### No Weather Data

Unlike F1 2024's packet format, **R3E's shared memory API does not expose weather or track condition fields**. Weather is effectively baked into track selection inside the game and is not surfaced as a telemetry value. The `weather_history` sampling step in `app.py` can be skipped or recorded as a static placeholder for RaceRoom sessions.

### Official & Community References

- **Official API**: [sector3studios/r3e-api](https://github.com/sector3studios/r3e-api) — C and C# struct definitions
- **Official WebHUD sample**: [sector3studios/webhud](https://github.com/sector3studios/webhud) — JavaScript consumer example
- **Python wrapper**: [Yuvix25/r3e-python-api](https://github.com/Yuvix25/r3e-python-api) — `pip install r3e-api`; provides dot-notation access (e.g. `R3ESharedMemory.get_value("Player.Velocity")`)
- **Forum thread**: [Shared Memory API — KW Studios forums](https://forum.kw-studios.com/index.php?threads/shared-memory-api.1525/)

---

## Files to Create

```
race_room/
├── PLAN.md            ← this document
├── __init__.py
├── config.py          ← shared memory name, poll rate, buffer settings
├── server.py          ← SharedMemoryReader (daemon thread, replaces UdpListener)
└── telemetry_state.py ← singleton with numpy circular buffers
```

---

## File-by-File Implementation Plan

### `race_room/config.py`

```python
SHARED_MEMORY_NAME = "$R3E"

# R3E API version this implementation targets
API_VERSION_MAJOR = 3
API_VERSION_MINOR = 5

# Poll rate and history buffer
TELEMETRY_HZ = 60          # poll shared memory at 60 Hz
HISTORY_SECS = 120         # keep 2 minutes of history
HISTORY_LEN = TELEMETRY_HZ * HISTORY_SECS  # 7200 samples

# Timeout: mark disconnected if no valid data for this many seconds
DISCONNECT_TIMEOUT_SECS = 2.0
```

---

### `race_room/server.py`

This replaces the socket-based `UdpListener`/`TcpListener` pattern with a **shared memory poller**.

```python
import mmap
import ctypes
import threading
import time
import struct
import logging

from race_room.config import SHARED_MEMORY_NAME, TELEMETRY_HZ, API_VERSION_MAJOR
from race_room.telemetry_state import state

logger = logging.getLogger(__name__)

class SharedMemoryReader(threading.Thread):
    """
    Polls the R3E shared memory region at TELEMETRY_HZ and pushes parsed
    data into the singleton TelemetryState. Runs as a daemon thread.
    """

    def __init__(self):
        super().__init__(daemon=True, name="RaceRoomSharedMemoryReader")
        self._stop_event = threading.Event()

    def run(self):
        interval = 1.0 / TELEMETRY_HZ
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except FileNotFoundError:
                # Game is not running; shared memory region doesn't exist yet
                pass
            except Exception as e:
                logger.warning("RaceRoom shared memory error: %s", e)
            time.sleep(interval)

    def _poll_once(self):
        # Open the named shared memory region (Windows only)
        # mmap.mmap(-1, 0, tagname=SHARED_MEMORY_NAME) opens a named mapping
        shmem = mmap.mmap(-1, _STRUCT_SIZE, tagname=SHARED_MEMORY_NAME,
                          access=mmap.ACCESS_READ)
        raw = shmem.read(_STRUCT_SIZE)
        shmem.close()

        parsed = _parse(raw)
        if parsed is not None:
            state.update(parsed)

    def stop(self):
        self._stop_event.set()
```

**`_parse(raw: bytes) -> dict | None`**

The parse function reads fields directly from the raw bytes using `struct.unpack_from()` with explicit byte offsets derived from the `r3e.h` / `R3E.cs` struct layout. An alternative (and simpler) approach is to define a `ctypes.Structure` subclass that mirrors the full C struct — this avoids manual offset arithmetic and is the approach used by `r3e-python-api`.

Key conversions to normalize to SimStrategist's internal units:

| R3E field | R3E unit | Normalized value |
|---|---|---|
| `CarSpeed` | m/s | × 3.6 → km/h |
| `EngineRps` | rad/s | × 9.549 → RPM |
| `FuelLeft` | liters | kept as liters |
| `TireTemp[*].CurrentTemp.Center` | °C | kept as °C |
| `TirePressure[*]` | kPa | kept as kPa |
| `BrakeBias` | 0.0–1.0 | × 100 → percentage |
| `Throttle`, `Brake`, `Clutch` | 0.0–1.0 | × 100 → percentage |
| `SteerInputRaw` | −1.0 to +1.0 | kept as-is |

The function returns a flat dict split into three sub-dicts for `state.update()`:

```python
{
    'telemetry': {
        'speed': float,        # km/h
        'rpm': float,
        'gear': int,           # -1=R, 0=N, 1+=forward
        'throttle': float,     # 0–100
        'brake': float,        # 0–100
        'clutch': float,       # 0–100
        'steer': float,        # -1.0 to 1.0
        'fuel': float,         # liters
        'fuel_per_lap': float, # liters (estimated, provided natively by R3E)
        'fuel_capacity': float,
        'engine_temp': float,  # °C
        'oil_temp': float,     # °C
        'tyre_temp': [float, float, float, float],  # center tread temp per wheel FL/FR/RL/RR
        'tyre_pressure': [float, float, float, float],  # kPa per wheel
        'tyre_wear': [float, float, float, float],  # 0.0–1.0 per wheel
        'brake_temp': [float, float, float, float], # °C per wheel
        'drs_equipped': bool,
        'drs_engaged': bool,
        'push_to_pass_engaged': bool,
        'abs_setting': int,
        'tc_setting': int,
        'pit_limiter': bool,
    },
    'lap_data': {
        'current_lap_time': float,   # seconds
        'last_lap_time': float,
        'best_lap_time': float,
        'sector1_time': float,
        'sector2_time': float,
        'car_position': int,
        'current_lap': int,
        'total_laps': int,
        'lap_distance_fraction': float,   # 0.0–1.0
        'pit_status': int,           # from InPitlane field
        'invalid_lap': bool,
        'time_delta_front': float,   # gap to car ahead (s)
        'time_delta_behind': float,
        'cut_track_warnings': int,
    },
    'session': {
        'track_name': str,
        'layout_name': str,
        'session_type': int,         # 0=Practice, 1=Qualify, 2=Race, 3=Warmup
        'session_phase': int,        # 4=Countdown, 5=Green, 6=Checkered
        'session_time_remaining': float,
        'num_vehicles': int,
        'fuel_use_active': bool,
        'tyre_wear_active': bool,
        # No weather fields — not available in R3E shared memory
    }
}
```

Return `None` if `VersionMajor != API_VERSION_MAJOR` (incompatible API version).

---

### `race_room/telemetry_state.py`

Follows the singleton + numpy circular buffer pattern from `f1/telemetry_state.py` and `forza_hrzn/telemetry_state.py`.

```python
import threading
import time
import numpy as np

from race_room.config import HISTORY_LEN, DISCONNECT_TIMEOUT_SECS

class TelemetryState:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._data_lock = threading.Lock()

        self.last_update_time = 0.0
        self.is_connected = False
        self.start_time = None

        # Circular buffer state
        self.history_maxlen = HISTORY_LEN
        self.history_index = 0
        self.history_count = 0

        # Numpy circular buffers (pre-allocated)
        self.buffer_time_stamp   = np.zeros(HISTORY_LEN, dtype=np.float32)
        self.buffer_speed_kmh    = np.zeros(HISTORY_LEN, dtype=np.float32)
        self.buffer_rpm          = np.zeros(HISTORY_LEN, dtype=np.float32)
        self.buffer_gear         = np.zeros(HISTORY_LEN, dtype=np.int8)
        self.buffer_throttle_pct = np.zeros(HISTORY_LEN, dtype=np.float32)
        self.buffer_brake_pct    = np.zeros(HISTORY_LEN, dtype=np.float32)

        # Current state dictionaries
        self.telemetry = {}
        self.lap_data  = {}
        self.session   = {}

    def update(self, parsed: dict):
        with self._data_lock:
            now = time.time()
            if self.start_time is None:
                self.start_time = now
            self.last_update_time = now
            self.is_connected = True

            t = parsed.get('telemetry', {})
            l = parsed.get('lap_data', {})
            s = parsed.get('session', {})

            self.telemetry.update(t)
            self.lap_data.update(l)
            self.session.update(s)

            # Write to circular buffers
            i = self.history_index
            self.buffer_time_stamp[i]   = now - self.start_time
            self.buffer_speed_kmh[i]    = t.get('speed', 0.0)
            self.buffer_rpm[i]          = t.get('rpm', 0.0)
            self.buffer_gear[i]         = t.get('gear', 0)
            self.buffer_throttle_pct[i] = t.get('throttle', 0.0)
            self.buffer_brake_pct[i]    = t.get('brake', 0.0)

            self.history_index = (i + 1) % self.history_maxlen
            self.history_count = min(self.history_count + 1, self.history_maxlen)

    def get_snapshot(self) -> dict:
        with self._data_lock:
            now = time.time()
            if self.last_update_time and (now - self.last_update_time) > DISCONNECT_TIMEOUT_SECS:
                self.is_connected = False
            return {
                'telemetry': dict(self.telemetry),
                'lap_data':  dict(self.lap_data),
                'session':   dict(self.session),
                'connected': self.is_connected,
            }

    def get_history_df(self):
        """Return a pandas DataFrame of the current circular buffer contents."""
        import pandas as pd
        with self._data_lock:
            n = self.history_count
            if n == 0:
                return pd.DataFrame()
            i = self.history_index
            # Reconstruct chronological order from circular buffer
            if n < self.history_maxlen:
                idx = slice(0, n)
            else:
                idx = list(range(i, self.history_maxlen)) + list(range(0, i))
            return pd.DataFrame({
                'time':     self.buffer_time_stamp[idx],
                'speed':    self.buffer_speed_kmh[idx],
                'rpm':      self.buffer_rpm[idx],
                'gear':     self.buffer_gear[idx],
                'throttle': self.buffer_throttle_pct[idx],
                'brake':    self.buffer_brake_pct[idx],
            })

state = TelemetryState()
```

---

### Integration in `app.py`

Following the existing pattern:

```python
# --- Import ---
from race_room.server import SharedMemoryReader as RaceRoomReader
from race_room.telemetry_state import state as race_room_state

# --- Daemon thread startup (inside the startup block) ---
_raceroom_reader = RaceRoomReader()
_raceroom_reader.start()
```

Weather sampling note: since R3E exposes no weather data, the `weather_sampler()` function in `app.py` should skip or stub out the RaceRoom branch, or simply record `None` for weather fields.

---

## Implementation Notes and Gotchas

### Windows-Only

RaceRoom runs only on Windows, and Windows named shared memory (`mmap.mmap(..., tagname=...)`) is not available on Linux or macOS. The `tagname` parameter is Windows-specific.

**Options if the Flask server runs on Linux:**
1. Run a small **relay agent** on the Windows gaming PC that reads `$R3E` and re-emits the data as UDP packets (similar to how RS Dash and Crew Chief work). This is the most practical path for a cross-platform server.
2. Run the entire Flask app on the same Windows machine as the game.

If a relay agent is implemented, the `server.py` listener reverts to a standard `UdpListener` socket pattern (identical to F1/Forza), receiving the relayed UDP packets. The relay script itself can use `r3e-python-api` (`pip install r3e-api`) for the Windows-side shared memory read.

### Struct Size

The full `Shared` struct is large (several hundred kilobytes when including all 128 `DriverData` competitor slots). Use `AllDriversOffset` and `DriverDataSize` from the header — do not hardcode the total struct size, as it changes between API versions.

Recommended approach: define a `ctypes.Structure` that only maps the header fields and the player fields (up to `AllDriversOffset`), then separately parse individual competitor entries from the tail of the buffer as needed.

### API Version Check

Always verify `VersionMajor == API_VERSION_MAJOR` before parsing the rest of the struct. If the version doesn't match, log a warning and return `None` from `_parse()` to avoid misaligned reads.

### Unit Conversions

| Field | R3E native unit | SimStrategist unit |
|---|---|---|
| `CarSpeed` | m/s | km/h (× 3.6) |
| `EngineRps` | rad/s | RPM (× 9.549) |
| `TirePressure` | kPa | kPa (no change) |
| `BrakeBias` | 0.0–1.0 | % (× 100) |
| `Throttle/Brake/Clutch` | 0.0–1.0 | % (× 100) |
| Sector times (sentinel) | −1.0 = not set | `None` |

### Competitor Array

R3E provides a full 128-slot competitor array (`DriverData[]`) with per-driver position, lap times, pit status, and sector splits. This is richer than LMU's current implementation. Initially, only the player's own `PlayerData` fields need to be parsed; the competitor array can be added later to support a live timing tower widget.

### ERS / Hybrid / EV Fields

R3E exposes `Voltage`, `ErsLevel`, `PowerMguH`, `PowerMguK`, `TorqueMguK`, `BatterySoC`, and `VirtualEnergy` fields for electric and hybrid car classes. These are absent from F1/LMU/Forza modules. They can be added to the `telemetry` dict and surfaced in the dashboard for R3E's EV and hybrid car classes.

---

## Recommended Implementation Order

1. **`config.py`** — define constants (trivial)
2. **`telemetry_state.py`** — implement singleton + circular buffers (copy-adapt from `forza_hrzn/telemetry_state.py`)
3. **`server.py`** (Windows, direct shared memory) — implement `SharedMemoryReader` with `ctypes.Structure` for player fields only; verify on a Windows machine with R3E running
4. **Relay agent** (optional, for cross-platform deployments) — small Python script on the gaming PC that reads `$R3E` and emits UDP; then `server.py` becomes a `UdpListener` identical to Forza
5. **`app.py` integration** — add import, start daemon thread, stub weather sampler
6. **Frontend** — add `'raceroom'` detection to `telemetry.js` `game family detection` block; reuse existing dashboard elements
7. **Extended fields** — add competitor array (timing tower), ERS/hybrid data, sector time deltas

---

## Comparison with Existing Implementations

| Aspect | F1 | LMU | Forza Horizon | RaceRoom |
|---|---|---|---|---|
| Protocol | UDP | TCP | UDP | Shared memory |
| Format | Binary struct | JSON | Binary struct | Binary struct (ctypes) |
| Port/address | 20777 | 5100 | 20055 | `$R3E` mapping name |
| Weather data | Yes (full) | Yes (ambient/track) | No | No |
| Competitor data | Yes (22 cars) | Partial | No | Yes (128 cars) |
| Pit window info | Yes | Partial | No | Yes (full) |
| Sector times | Yes | Yes | No | Yes (3 per driver) |
| ERS / hybrid | Yes (F1 2022+) | No | No | Yes |
| Platform | Cross-platform | Cross-platform | Cross-platform | Windows only (or relay) |
| Update rate | ~20 Hz (UDP send) | ~60 Hz (TCP send) | ~60 Hz (UDP send) | Up to 512 Hz (poll at 60) |
