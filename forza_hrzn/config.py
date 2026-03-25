"""
Forza Horizon Telemetry Configuration
"""

UDP_IP       = '0.0.0.0'
FH4_PORT     = 20044
FH5_PORT     = 20055
BUFFER_SIZE  = 1024
TELEMETRY_HZ = 60    # Forza sends at ~60 Hz (vs F1's 20 Hz)
HISTORY_SECS = 120
HISTORY_LEN  = TELEMETRY_HZ * HISTORY_SECS  # 7 200 points

# Packet size → game version
VERSION_BY_SIZE = {
    324: 'fh4',
    323: 'fh5',
}
