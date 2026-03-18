"""
LMU Telemetry Dashboard Configuration
Centralized configuration management for all Le Mans Ultimate dashboard settings.
"""


class Config:
    """Main configuration class for the LMU Telemetry Dashboard"""

    # ============================================================================
    # TCP SETTINGS
    # LMU uses the "Ultimate Telemetry Socket – JSON Telemetry Plugin" over TCP/UDP.
    # Default mode is a persistent TCP connection; UDP is available via --udp flag.
    # ============================================================================
    TCP_HOST    = '127.0.0.1'
    TCP_PORT    = 5100
    UDP_HOST    = '127.0.0.1'
    UDP_PORT    = 5100
    UDP_BUFSIZE = 65535   # max UDP datagram; TCP uses readline

    # ============================================================================
    # PERFORMANCE SETTINGS
    # ============================================================================
    # Maximum telemetry history length (points)
    # LMU plugin sends at up to 60 Hz; 600 points ≈ 10 seconds of history.
    # Increase to 3600 for 60 seconds if memory allows.
    MAX_HISTORY_LENGTH = 600

    # Maximum points to render in charts before downsampling
    CHART_MAX_POINTS = 5000

    # Enable WebGL rendering for better performance
    ENABLE_WEBGL = True

    # Cache size for memoization (number of function calls)
    CACHE_SIZE = 128

    # Seconds without data before the connection is marked as lost
    STALE_TIMEOUT = 2.0

    # ============================================================================
    # UI SETTINGS
    # ============================================================================
    DEFAULT_THEME = "dark"

    # Chart update rate for live mode (milliseconds)
    CHART_UPDATE_RATE = 500

    # Animation update rate (milliseconds)
    ANIMATION_UPDATE_RATE = 100

    # Default port for Dash/Flask server
    SERVER_PORT = 5051
    SERVER_DEBUG = True

    # ============================================================================
    # DATA SETTINGS
    # ============================================================================
    # Speed unit conversion: plugin sends m/s; multiply by this to get kph
    SPEED_MS_TO_KPH = 3.6

    # RPM ceiling used to approximate rev-light percentage (LMU has no dedicated field)
    RPM_MAX_ESTIMATE = 12000

    # Required telemetry fields (all present in every plugin update)
    REQUIRED_TELEMETRY_FIELDS = ['speed', 'rpm', 'gear', 'throttle', 'brake']

    # Optional telemetry fields (may be absent in some plugin versions)
    OPTIONAL_TELEMETRY_FIELDS = [
        'clutch', 'steer', 'fuel',
        'engine_water_temp', 'engine_oil_temp',
    ]

    # Lap/timing fields sent by the plugin
    LAP_FIELDS = [
        'current_lap_time', 'last_lap_time', 'best_lap_time',
        'sector1_time', 'sector2_time',
        'current_lap', 'car_position', 'pit_status',
    ]

    # Session fields sent by the plugin
    SESSION_FIELDS = [
        'track_name', 'session_type', 'flag',
        'ambient_temp', 'track_temp', 'num_vehicles',
    ]

    # ============================================================================
    # SESSION FLAGS
    # ============================================================================
    # The plugin sends a string flag; map it to a display label and color key.
    FLAG_MAP = {
        'green':      ('Green',     'positive'),
        'yellow':     ('Yellow',    'warning'),
        'red':        ('Red',       'negative'),
        'chequered':  ('Chequered', 'text_primary'),
        '':           ('--',        'text_muted'),
    }

    # ============================================================================
    # LMU THEME COLORS
    # Inspired by the ACO / FIA WEC identity used in Le Mans Ultimate.
    # ============================================================================
    COLORS = {
        # Core backgrounds
        'card_bg':    '#141414',
        'background': '#0d0d0d',

        # LMU / ACO signature colors
        'lmu_blue':   '#0057b8',   # ACO/WEC primary blue
        'lmu_gold':   '#d4a017',   # ACO gold / Le Mans trophy gold
        'lmu_silver': '#c0c0c0',   # LMP1/Hypercar bodywork silver

        # Text colors
        'text_primary':   '#ffffff',
        'text_secondary': '#8a8a8a',
        'text_accent':    '#0057b8',
        'text_muted':     '#666666',

        # Chart colors
        'grid_line': 'rgba(255, 255, 255, 0.05)',
        'border':    'rgba(255, 255, 255, 0.08)',

        # Data series colors — WEC class colors
        'series': [
            '#d4a017',   # Hypercar gold
            '#ff0000',   # LMP2 red
            '#0057b8',   # GTE/GT3 blue
            '#00c87a',   # positive green
            '#ff4757',   # alert red
        ],

        # Data state colors
        'positive': '#00c87a',
        'negative': '#ff4757',
        'warning':  '#ffa502',

        # Table colors
        'table_header':         '#0d0d0d',
        'table_row_even':       '#141414',
        'table_row_odd':        '#1a1a1a',
        'header_gradient_start': '#0057b8',
    }

    # ============================================================================
    # STYLE PRESETS
    # ============================================================================
    CARD_STYLE = {
        'backgroundColor': COLORS['card_bg'],
        'borderRadius': '12px',
        'padding': '20px',
        'marginBottom': '20px',
        'border': f'1px solid {COLORS["border"]}',
        'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.3)',
    }

    SECTION_TITLE_STYLE = {
        'fontSize': '16px',
        'fontWeight': '700',
        'color': COLORS['text_primary'],
        'letterSpacing': '0.08em',
        'marginBottom': '15px',
        'textTransform': 'uppercase',
        'borderBottom': f'2px solid {COLORS["header_gradient_start"]}',
        'paddingBottom': '8px',
        'fontFamily': 'Orbitron, sans-serif',
    }

    METRIC_VALUE_STYLE = {
        'fontSize': '32px',
        'fontWeight': '700',
        'color': COLORS['lmu_gold'],
        'fontFamily': 'Orbitron, sans-serif',
        'textShadow': '0 0 30px rgba(212, 160, 23, 0.4)',
        'transition': 'text-shadow 0.3s ease',
    }

    METRIC_LABEL_STYLE = {
        'fontSize': '12px',
        'color': COLORS['text_secondary'],
        'marginTop': '5px',
        'textTransform': 'uppercase',
        'letterSpacing': '0.05em',
    }

    DROPDOWN_STYLE = {
        'backgroundColor': COLORS['card_bg'],
        'borderRadius': '6px',
    }

    @classmethod
    def get_chart_config(cls):
        """Returns standard configuration for Plotly charts."""
        return {
            'displayModeBar': False,
            'scrollZoom': False,
        }

    @classmethod
    def get_chart_layout_base(cls):
        """Returns base layout configuration for Plotly charts."""
        return {
            'template': 'plotly_dark',
            'paper_bgcolor': cls.COLORS['card_bg'],
            'plot_bgcolor':  cls.COLORS['card_bg'],
            'font': {'color': cls.COLORS['text_secondary'], 'size': 11},
            'margin': {'l': 50, 'r': 20, 't': 40, 'b': 50},
            'xaxis': {'gridcolor': cls.COLORS['grid_line']},
            'yaxis': {'gridcolor': cls.COLORS['grid_line']},
            'hovermode': 'closest',
        }
