"""
LMU Telemetry State Management
Thread-safe singleton with circular buffer, mirroring F1 telemetry_state.py
"""
import threading
import time
import numpy as np
from typing import Dict, Any, Optional


MAX_HISTORY_LENGTH = 600  # ~10 seconds at 60 Hz


class LMUTelemetryState:
    """Thread-safe singleton for LMU telemetry data."""

    _instance: Optional['LMUTelemetryState'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'LMUTelemetryState':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._initialized = True
        self.last_update_time: float = 0
        self.is_connected: bool = False
        self.start_time: float = time.time()

        # Circular buffer
        self.history_maxlen: int = MAX_HISTORY_LENGTH
        self.history_index: int = 0
        self.history_count: int = 0

        self._init_circular_buffer()

        self.telemetry: Dict[str, Any] = {
            'speed': 0.0,       # m/s from plugin; converted to kph on read
            'rpm': 0,
            'gear': 0,          # 0 = neutral, -1 = reverse
            'throttle': 0.0,    # 0.0–1.0
            'brake': 0.0,       # 0.0–1.0
            'clutch': 0.0,      # 0.0–1.0
            'steer': 0.0,       # -1.0 (left) to 1.0 (right)
            'fuel': 0.0,        # kg remaining
            'engine_water_temp': 0.0,
            'engine_oil_temp': 0.0,
        }

        self.lap_data: Dict[str, Any] = {
            'current_lap_time': 0.0,
            'last_lap_time': 0.0,
            'best_lap_time': 0.0,
            'sector1_time': 0.0,
            'sector2_time': 0.0,
            'current_lap': 0,
            'car_position': 0,
            'pit_status': 0,    # 0 = on track, 1 = in pit lane, 2 = in pit box
        }

        self.session: Dict[str, Any] = {
            'track_name': '',
            'session_type': '',
            'flag': '',         # green / yellow / red / chequered
            'ambient_temp': 0.0,
            'track_temp': 0.0,
            'num_vehicles': 0,
        }

    def _init_circular_buffer(self) -> None:
        size = self.history_maxlen
        self.buffer_time_stamp   = np.zeros(size, dtype=np.float32)
        self.buffer_speed_kph    = np.zeros(size, dtype=np.float32)
        self.buffer_rpm          = np.zeros(size, dtype=np.float32)
        self.buffer_gear         = np.zeros(size, dtype=np.int8)
        self.buffer_throttle_pct = np.zeros(size, dtype=np.float32)
        self.buffer_brake_pct    = np.zeros(size, dtype=np.float32)

    def update_telemetry(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self.telemetry.update(data)
            self.last_update_time = time.time()
            self.is_connected = True

            if self.history_count == 0:
                self.start_time = self.last_update_time

            relative_time = self.last_update_time - self.start_time
            speed_kph = data.get('speed', 0) * 3.6  # m/s → kph

            idx = self.history_index
            self.buffer_time_stamp[idx]   = relative_time
            self.buffer_speed_kph[idx]    = speed_kph
            self.buffer_rpm[idx]          = data.get('rpm', 0)
            self.buffer_gear[idx]         = max(-128, min(data.get('gear', 0), 127))
            self.buffer_throttle_pct[idx] = data.get('throttle', 0) * 100
            self.buffer_brake_pct[idx]    = data.get('brake', 0) * 100

            self.history_index = (self.history_index + 1) % self.history_maxlen
            self.history_count = min(self.history_count + 1, self.history_maxlen)

    def update_lap_data(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self.lap_data.update(data)
            self.last_update_time = time.time()
            self.is_connected = True

    def update_session(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self.session.update(data)
            self.last_update_time = time.time()
            self.is_connected = True

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            if time.time() - self.last_update_time > 2.0:
                self.is_connected = False
            return {
                'telemetry': self.telemetry.copy(),
                'lap_data':  self.lap_data.copy(),
                'session':   self.session.copy(),
                'connected': self.is_connected,
            }


# Global singleton
state = LMUTelemetryState()
