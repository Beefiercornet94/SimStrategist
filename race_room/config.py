"""
RaceRoom Racing Experience Telemetry Configuration
"""

POLL_HZ          = 60     # shared memory poll rate
HISTORY_SECS     = 120
HISTORY_LEN      = POLL_HZ * HISTORY_SECS  # 7 200 points
DISCONNECT_TIMEOUT = 2.0  # seconds before marking disconnected