"""
Weather History Tracker
Thread-safe singleton that records weather and temperature snapshots per game.
Entries are added when weather code or temps change by a meaningful amount.
"""
import threading
import time

WEATHER_DESC = {
    0: 'Clear',
    1: 'Light Cloud',
    2: 'Overcast',
    3: 'Light Rain',
    4: 'Heavy Rain',
    5: 'Storm',
}

MAX_ENTRIES = 200


class WeatherHistory:
    _instance = None
    _class_lock = threading.Lock()

    def __init__(self):
        self._lock = threading.Lock()
        self._data  = {'f1': [], 'lmu': []}
        self._last  = {'f1': None, 'lmu': None}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def record(self, game: str, lap: int, weather: int,
               track_temp: float, air_temp: float) -> None:
        """
        Store a snapshot if weather code or temps have changed meaningfully.
        For LMU (no weather code), pass weather=0 and rely on temp deltas.
        """
        with self._lock:
            last = self._last[game]
            changed = (
                last is None
                or weather != last['weather']
                or abs(track_temp - last['track_temp']) >= 2
                or abs(air_temp  - last['air_temp'])   >= 2
            )
            if not changed:
                return

            entry = {
                'timestamp':   time.time(),
                'lap':         lap,
                'weather':     weather,
                'weather_desc': WEATHER_DESC.get(weather, 'Unknown'),
                'track_temp':  round(float(track_temp), 1),
                'air_temp':    round(float(air_temp),   1),
            }
            self._last[game] = entry
            self._data[game].append(entry)
            if len(self._data[game]) > MAX_ENTRIES:
                self._data[game] = self._data[game][-MAX_ENTRIES:]

    def get_history(self, game: str, limit: int = 50) -> list:
        with self._lock:
            return list(self._data[game][-limit:])

    def clear(self, game: str) -> None:
        with self._lock:
            self._data[game] = []
            self._last[game] = None


# Module-level singleton
weather_history = WeatherHistory.get_instance()
