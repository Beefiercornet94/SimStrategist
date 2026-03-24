"""
AI Strategy Analyser
Uses the OpenAI API (gpt-4o-mini) to produce three race strategies:
  - standard : optimal single/multi-stop based on current conditions
  - push     : aggressive; higher tyre/fuel usage, faster lap times
  - save     : conservative; tyre/fuel management, longer stints

Each strategy includes a stop plan, estimated total race time, and a time delta
relative to the standard strategy (negative = faster, positive = slower).
"""
import json
import os

from strategy.weather_history import weather_history, WEATHER_DESC

# ── Compound look-up tables ────────────────────────────────────────────────────
# F1 2023/2024 visual compound IDs
VISUAL_COMPOUND = {
    16: 'Soft',
    17: 'Medium',
    18: 'Hard',
    7:  'Intermediate',
    8:  'Wet',
}

COMPOUND_COLOUR = {
    'Soft':         '#e8002d',
    'Medium':       '#ffd000',
    'Hard':         '#f0f0ec',
    'Intermediate': '#43b02a',
    'Wet':          '#0067ff',
    'Unknown':      '#888888',
}


def _fmt_ms(ms: int) -> str:
    if not ms:
        return '--:--.---'
    m  = ms // 60000
    s  = (ms % 60000) // 1000
    mi = ms % 1000
    return f"{m}:{s:02d}.{mi:03d}"


def _fmt_sec(s: float) -> str:
    if not s:
        return '--:--.---'
    m  = int(s // 60)
    sc = int(s % 60)
    mi = round((s % 1) * 1000)
    return f"{m}:{sc:02d}.{mi:03d}"


def _build_prompt(ctx: dict) -> str:
    weather_lines = '\n'.join(
        f"  Lap {e['lap']:>3}: {e['weather_desc']:<12}  "
        f"Track {e['track_temp']}°C  Air {e['air_temp']}°C"
        for e in ctx['weather_history']
    ) or '  No history recorded yet'

    tyre_wear = ctx['tyre_wear']
    wear_str = (
        f"FL={tyre_wear[0]:.1f}%  FR={tyre_wear[1]:.1f}%  "
        f"RL={tyre_wear[2]:.1f}%  RR={tyre_wear[3]:.1f}%"
        if any(w > 0 for w in tyre_wear)
        else 'Not available'
    )

    laps_remaining = ctx['laps_remaining']
    laps_str = str(laps_remaining) if laps_remaining is not None else 'Unknown'

    return f"""You are an expert motorsport race strategist. Analyse the telemetry below and produce exactly three pit-stop strategies as a single JSON object.

## Current Race State
Game            : {ctx['game'].upper()}
Current Lap     : {ctx['current_lap']} / {ctx['total_laps'] or 'Unknown'}
Laps Remaining  : {laps_str}
Car Position    : {ctx['car_position']}
Tyre Compound   : {ctx['compound']}
Tyre Age        : {ctx['tyre_age']} laps
Tyre Wear       : {wear_str}
{ctx['fuel_line']}
Best Lap Time   : {ctx['best_lap_fmt']}
Last Lap Time   : {ctx['last_lap_fmt']}
Penalties       : {ctx['penalties']}s

## Track Conditions
Weather         : {ctx['weather_desc']}
Track Temp      : {ctx['track_temp']}°C
Air Temp        : {ctx['air_temp']}°C

## Weather / Conditions History (oldest → newest)
{weather_lines}

## Output Instructions
Produce exactly three strategies:
  1. "standard" — optimal strategy for current pace and conditions
  2. "push"     — aggressive; softer compounds, more stops, faster lap times, higher tyre/fuel usage
  3. "save"     — conservative; harder compounds, fewer/later stops, tyre and fuel management

Respond with ONLY valid JSON — no markdown fences, no commentary.
Use this exact schema:
{{
  "standard": {{
    "name": "Standard",
    "stops": <int>,
    "stint_plan": [
      {{"compound": "<name>", "laps": <int>, "notes": "<brief note>"}},
      ...
    ],
    "delta_seconds": 0,
    "est_total_time": "<H:MM:SS or MM:SS>",
    "summary": "<1-2 sentence rationale>"
  }},
  "push": {{
    "name": "Push",
    "stops": <int>,
    "stint_plan": [...],
    "delta_seconds": <negative int — push is faster than standard>,
    "est_total_time": "<H:MM:SS or MM:SS>",
    "summary": "<1-2 sentence rationale>"
  }},
  "save": {{
    "name": "Save",
    "stops": <int>,
    "stint_plan": [...],
    "delta_seconds": <positive int — save is slower than standard>,
    "est_total_time": "<H:MM:SS or MM:SS>",
    "summary": "<1-2 sentence rationale>"
  }}
}}

Rules:
- Base tyre wear rates on the compound and laps already completed.
- Push strategy increases per-lap tyre wear by ~30 %; Save reduces it by ~20 %.
- If fuel data is available, factor fuel usage into lap-count estimates.
- If weather is deteriorating (rain incoming), bias strategies toward intermediates/wets.
- delta_seconds is relative to standard (standard is always 0).
- If total laps are unknown, make reasonable assumptions for a ~30-lap sprint or ~50-lap feature race."""


def analyze_strategy(game: str) -> dict:
    """
    Build a context dict from live telemetry + weather history and ask
    Claude for three race strategies.  Returns the parsed JSON dict.
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return {'error': 'OPENAI_API_KEY environment variable is not set'}

    # Lazy import to avoid circular deps at module load time
    from f1.telemetry_state import state as f1_state
    from lmu.telemetry_state import state as lmu_state

    src  = lmu_state if game == 'lmu' else f1_state
    snap = src.get_snapshot()

    if not snap['connected']:
        return {'error': 'No live telemetry — ensure the game is running'}

    t    = snap['telemetry']
    lap  = snap['lap_data']
    sess = snap['session']

    is_f1 = (game == 'f1')

    # ── Tyre info ──────────────────────────────────────────────────────────────
    if is_f1:
        visual_id = t.get('tyre_visual_compound')
        compound  = VISUAL_COMPOUND.get(visual_id, 'Unknown') if visual_id else 'Unknown'
        tyre_age  = int(t.get('tyre_age_laps', 0) or 0)
        tyre_wear = [round(float(v), 1) for v in t.get('tyre_wear', [0, 0, 0, 0])]
        fuel_in_tank      = t.get('fuel_in_tank', 0) or 0
        fuel_remaining_laps = t.get('fuel_remaining_laps', 0) or 0
        fuel_line = (
            f"Fuel in Tank    : {fuel_in_tank:.1f} kg  "
            f"(~{fuel_remaining_laps:.1f} laps remaining)"
        )
        best_lap_fmt = _fmt_ms(lap.get('best_lap_time', 0))
        last_lap_fmt = _fmt_ms(lap.get('last_lap_time', 0))
        weather      = sess.get('weather', 0)
        weather_desc = WEATHER_DESC.get(weather, 'Unknown')
        track_temp   = sess.get('track_temperature', 0)
        air_temp     = sess.get('air_temperature', 0)
    else:
        compound  = 'Unknown'
        tyre_age  = 0
        tyre_wear = [0.0, 0.0, 0.0, 0.0]
        fuel_val  = t.get('fuel', 0) or 0
        fuel_line = f"Fuel in Tank    : {fuel_val:.1f} kg"
        best_lap_fmt = _fmt_sec(lap.get('best_lap_time', 0))
        last_lap_fmt = _fmt_sec(lap.get('last_lap_time', 0))
        flag         = sess.get('flag', 'green').lower()
        weather      = 3 if 'rain' in flag else 0
        weather_desc = 'Rain' if 'rain' in flag else 'Dry'
        track_temp   = sess.get('track_temp', 0)
        air_temp     = sess.get('ambient_temp', 0)

    current_lap   = int(lap.get('current_lap', 0) or 0)
    total_laps    = int(sess.get('total_laps', 0) or 0)
    laps_remaining = max(0, total_laps - current_lap) if total_laps else None

    ctx = {
        'game':           game,
        'current_lap':    current_lap,
        'total_laps':     total_laps or None,
        'laps_remaining': laps_remaining,
        'car_position':   lap.get('car_position', '--'),
        'compound':       compound,
        'tyre_age':       tyre_age,
        'tyre_wear':      tyre_wear,
        'fuel_line':      fuel_line,
        'best_lap_fmt':   best_lap_fmt,
        'last_lap_fmt':   last_lap_fmt,
        'penalties':      lap.get('penalties', 0),
        'weather_desc':   weather_desc,
        'track_temp':     track_temp,
        'air_temp':       air_temp,
        'weather_history': weather_history.get_history(game, limit=20),
    }

    prompt = _build_prompt(ctx)

    client   = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model      = 'gpt-4o-mini',
        max_tokens = 1500,
        messages   = [{'role': 'user', 'content': prompt}],
    )

    raw = response.choices[0].message.content.strip()
    # Strip accidental markdown fences
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[1]
        raw = raw.rsplit('```', 1)[0]

    result = json.loads(raw)

    # Attach compound colours for the frontend
    for strat in result.values():
        for stint in strat.get('stint_plan', []):
            stint['colour'] = COMPOUND_COLOUR.get(stint.get('compound', ''), '#888888')

    return result
