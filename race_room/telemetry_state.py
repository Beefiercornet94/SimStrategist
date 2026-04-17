"""
RaceRoom Telemetry State Management
Thread-safe singleton with circular buffer — mirrors the forza_hrzn/telemetry_state.py interface.
"""

import threading
import time
import numpy as np
import pandas as pd
from typing import Any, Dict, Optional

from race_room.config import DISCONNECT_TIMEOUT, HISTORY_LEN


class TelemetryState:
    """
    Thread-safe singleton for RaceRoom telemetry.

    Public interface matches forza_hrzn/telemetry_state.py:
      state.update(parsed_dict)
      state.get_snapshot() -> dict
      state.get_history_df() -> DataFrame
    """

    _instance: Optional['TelemetryState'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'TelemetryState':
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

        self.last_update_time: float = 0.0
        self.is_connected: bool = False
        self.start_time: float = time.time()

        self.history_maxlen: int = HISTORY_LEN
        self.history_index: int = 0
        self.history_count: int = 0

        size = self.history_maxlen
        self.buffer_time_stamp   = np.zeros(size, dtype=np.float32)
        self.buffer_speed_kmh    = np.zeros(size, dtype=np.float32)
        self.buffer_rpm          = np.zeros(size, dtype=np.float32)
        self.buffer_gear         = np.zeros(size, dtype=np.int8)
        self.buffer_throttle_pct = np.zeros(size, dtype=np.float32)
        self.buffer_brake_pct    = np.zeros(size, dtype=np.float32)

        self.telemetry: Dict[str, Any] = {
            'speed_kmh':     0.0,
            'rpm':           0.0,
            'gear':          0,
            'throttle':      0.0,
            'brake':         0.0,
            'clutch':        0.0,
            'steer':         0.0,
            'fuel':          0.0,
            'fuel_per_lap':  0.0,
            'engine_temp':   0.0,
            'tyre_temp':     [0.0, 0.0, 0.0, 0.0],
            'tyre_pressure': [0.0, 0.0, 0.0, 0.0],
            'tyre_wear':     [0.0, 0.0, 0.0, 0.0],
        }
        self.lap_data: Dict[str, Any] = {
            'current_lap_time': 0.0,
            'last_lap_time':    0.0,
            'best_lap_time':    0.0,
            'car_position':     0,
            'current_lap':      0,
            'pit_status':       0,
        }
        self.session: Dict[str, Any] = {
            'track_name':             '',
            'layout_name':            '',
            'session_type':           -1,
            'session_time_remaining': 0.0,
            'num_vehicles':           0,
        }

    def update(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self.telemetry.update({k: data[k] for k in self.telemetry if k in data})
            self.lap_data.update({k: data[k] for k in self.lap_data if k in data})
            self.session.update({k: data[k] for k in self.session if k in data})

            self.last_update_time = time.time()
            self.is_connected = True

            if self.history_count == 0:
                self.start_time = self.last_update_time
            relative_time = self.last_update_time - self.start_time

            idx = self.history_index
            self.buffer_time_stamp[idx]   = relative_time
            self.buffer_speed_kmh[idx]    = data.get('speed_kmh', 0)
            self.buffer_rpm[idx]          = data.get('rpm', 0)
            self.buffer_gear[idx]         = max(-128, min(data.get('gear', 0), 127))
            self.buffer_throttle_pct[idx] = data.get('throttle', 0) * 100
            self.buffer_brake_pct[idx]    = data.get('brake', 0) * 100

            self.history_index = (self.history_index + 1) % self.history_maxlen
            self.history_count = min(self.history_count + 1, self.history_maxlen)

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            if time.time() - self.last_update_time > DISCONNECT_TIMEOUT:
                self.is_connected = False
            return {
                'telemetry': self.telemetry.copy(),
                'lap_data':  self.lap_data.copy(),
                'session':   self.session.copy(),
                'connected': self.is_connected,
            }

    def get_history_df(self, limit: Optional[int] = None) -> pd.DataFrame:
        with self._lock:
            if self.history_count == 0:
                return pd.DataFrame()

            if self.history_count < self.history_maxlen:
                indices = slice(0, self.history_count)
            else:
                if limit and limit < self.history_count:
                    start = (self.history_index - limit) % self.history_maxlen
                else:
                    start = self.history_index
                end = self.history_index
                if end > start:
                    indices = slice(start, end)
                else:
                    indices = np.concatenate([
                        np.arange(start, self.history_maxlen),
                        np.arange(0, end),
                    ])

            return pd.DataFrame({
                'time_stamp':   self.buffer_time_stamp[indices],
                'speed_kmh':    self.buffer_speed_kmh[indices],
                'rpm':          self.buffer_rpm[indices],
                'gear':         self.buffer_gear[indices],
                'throttle_pct': self.buffer_throttle_pct[indices],
                'brake_pct':    self.buffer_brake_pct[indices],
            })


# Global singleton
state = TelemetryState()
