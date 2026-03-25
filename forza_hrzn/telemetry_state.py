"""
Forza Horizon Telemetry State Management
Thread-safe singleton with circular buffer — mirrors the f1/telemetry_state.py interface.
"""

import threading
import time
import pandas as pd
import numpy as np
from typing import Any, Dict, Optional

from forza_hrzn.config import HISTORY_LEN


class TelemetryState:
    """
    Thread-safe singleton for Forza Horizon telemetry.

    Public interface matches f1/telemetry_state.py so app.py can treat both
    identically:
      state.update(parsed_dict)
      state.get_snapshot() -> dict
      state.get_history_df() -> DataFrame
      state.connected: bool
      state.last_update_time: float
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
        self.game_version: str = 'unknown'
        self.start_time: float = time.time()

        # Circular buffer bookkeeping
        self.history_maxlen: int = HISTORY_LEN
        self.history_index: int = 0
        self.history_count: int = 0

        self._init_circular_buffer()

        # Latest packet store
        self.telemetry: Dict[str, Any] = {
            'is_race_on':     0,
            'rpm':            0,
            'max_rpm':        0,
            'speed_kmh':      0.0,
            'gear':           0,
            'throttle':       0.0,
            'brake':          0.0,
            'clutch':         0.0,
            'steer':          0.0,
            'tyre_temp':      [0.0, 0.0, 0.0, 0.0],
            'fuel':           0.0,
            'boost':          0.0,
            'car_class':      0,
            'car_perf_index': 0,
        }
        self.lap_data: Dict[str, Any] = {
            'lap_number':    0,
            'current_lap':   0.0,
            'last_lap':      0.0,
            'best_lap':      0.0,
            'race_position': 0,
        }

    def _init_circular_buffer(self) -> None:
        size = self.history_maxlen
        self.buffer_time_stamp   = np.zeros(size, dtype=np.float32)
        self.buffer_speed_kmh    = np.zeros(size, dtype=np.float32)
        self.buffer_rpm          = np.zeros(size, dtype=np.float32)
        self.buffer_gear         = np.zeros(size, dtype=np.int8)
        self.buffer_throttle_pct = np.zeros(size, dtype=np.float32)
        self.buffer_brake_pct    = np.zeros(size, dtype=np.float32)

    def update(self, data: Dict[str, Any]) -> None:
        """Update state from a parsed Forza packet dict."""
        with self._lock:
            self.telemetry.update({k: data[k] for k in self.telemetry if k in data})
            self.lap_data.update({k: data[k] for k in self.lap_data if k in data})
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

    @property
    def connected(self) -> bool:
        return self.is_connected

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            if time.time() - self.last_update_time > 2.0:
                self.is_connected = False
            return {
                'telemetry':    self.telemetry.copy(),
                'lap_data':     self.lap_data.copy(),
                'session':      {'game_version': self.game_version},
                'connected':    self.is_connected,
            }

    def get_history_df(self, limit: Optional[int] = None) -> pd.DataFrame:
        with self._lock:
            if self.history_count == 0:
                return pd.DataFrame()

            if self.history_count < self.history_maxlen:
                slice_start = 0
                slice_end   = self.history_count
            else:
                if limit and limit < self.history_count:
                    slice_start = (self.history_index - limit) % self.history_maxlen
                else:
                    slice_start = self.history_index
                slice_end = self.history_index

            if slice_end > slice_start:
                indices = slice(slice_start, slice_end)
            else:
                indices = np.concatenate([
                    np.arange(slice_start, self.history_maxlen),
                    np.arange(0, slice_end),
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
