"""
F1 Telemetry Dashboard Configuration
Centralized configuration management for all dashboard settings.
"""

class Config:
    """Main configuration class for the F1 Telemetry Dashboard"""
    
    # ============================================================================
    # UDP SETTINGS
    # ============================================================================
    UDP_IP = "0.0.0.0"
    UDP_PORT = 20777
    UDP_BUFFER_SIZE = 2048
    
    # ============================================================================
    # PERFORMANCE SETTINGS
    # ============================================================================
    # Maximum telemetry history length (points)
    # At 20Hz, 2400 points = 120 seconds of history
    MAX_HISTORY_LENGTH = 2400
    
    # Maximum points to render in charts before downsampling
    CHART_MAX_POINTS = 5000
    
    # Enable WebGL rendering for better performance
    ENABLE_WEBGL = True
    
    # Cache size for memoization (number of function calls)
    CACHE_SIZE = 128
    
    # ============================================================================
    # UI SETTINGS
    # ============================================================================
    DEFAULT_THEME = "dark"
    
    # Chart update rate for live mode (milliseconds)
    CHART_UPDATE_RATE = 500
    
    # Animation update rate (milliseconds)
    ANIMATION_UPDATE_RATE = 100
    
    # Default port for Dash server
    SERVER_PORT = 8050
    SERVER_DEBUG = True
    
    # ============================================================================
    # DATA SETTINGS
    # ============================================================================
    # Default data file path
    DEFAULT_DATA_PATH = "data/example_telemetry.csv"
    
    # Required CSV columns
    REQUIRED_COLUMNS = ['driver', 'lap', 'time_stamp']
    
    # Optional CSV columns
    OPTIONAL_COLUMNS = [
        'speed_kph', 'rpm', 'throttle_pct', 'brake_pct', 
        'gear', 'drs', 'sector', 'sector_time_ms', 'lat', 'long'
    ]
    
    # ============================================================================
    # F1 THEME COLORS
    # ============================================================================
    COLORS = {
        # Core backgrounds
        'card_bg': '#141414',
        'background': '#0d0d0d',
        
        # F1 Signature colors
        'f1_red': '#e10600',
        'f1_cyan': '#00d2be',
        'f1_gold': '#f0c514',
        
        # Text colors
        'text_primary': '#ffffff',
        'text_secondary': '#8a8a8a',
        'text_accent': '#00d2be',
        'text_muted': '#666666',
        
        # Chart colors
        'grid_line': 'rgba(255, 255, 255, 0.05)',
        'border': 'rgba(255, 255, 255, 0.08)',
        
        # Data series colors - F1 team inspired
        'series': ['#e10600', '#00d2be', '#f0c514', '#00ff87', '#ff4757'],
        
        # Data state colors
        'positive': '#00ff87',
        'negative': '#ff4757',
        'warning': '#ffa502',
        
        # Table colors
        'table_header': '#0d0d0d',
        'table_row_even': '#141414',
        'table_row_odd': '#1a1a1a',
        'header_gradient_start': '#e10600',
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
        'color': COLORS['f1_cyan'],
        'fontFamily': 'Orbitron, sans-serif',
        'textShadow': '0 0 30px rgba(0, 210, 190, 0.4)',
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
        """Returns standard configuration for Plotly charts"""
        return {
            'displayModeBar': False,
            'scrollZoom': False,
        }
    
    @classmethod
    def get_chart_layout_base(cls):
        """Returns base layout configuration for Plotly charts"""
        return {
            'template': 'plotly_dark',
            'paper_bgcolor': cls.COLORS['card_bg'],
            'plot_bgcolor': cls.COLORS['card_bg'],
            'font': {'color': cls.COLORS['text_secondary'], 'size': 11},
            'margin': {'l': 50, 'r': 20, 't': 40, 'b': 50},
            'xaxis': {'gridcolor': cls.COLORS['grid_line']},
            'yaxis': {'gridcolor': cls.COLORS['grid_line']},
            'hovermode': 'closest',
        }