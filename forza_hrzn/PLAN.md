# Forza Horizon Telemetry — Implementation Plan

This document describes how Forza Horizon games send telemetry data, how the format differs between titles, and how a `forza_hrzn/` listener should be implemented to match the architecture used by `f1/` and `lmu/`.

---

## How Forza Horizon Sends Telemetry

Forza Horizon games broadcast a **single binary UDP packet** at approximately **60 Hz** to a configurable IP and port. There is no handshake, no session header, and no packet ID scheme — every datagram is a complete snapshot of the current vehicle state.

Unlike the F1 UDP format, there is no official public specification from Microsoft / Turn 10 Studios. The field layout below is community-reverse-engineered and is widely used in open-source projects, but byte offsets should be verified against a known-good implementation before shipping.

### In-game setup

All Forza Horizon titles expose telemetry output under:

> **Settings → Gameplay & HUD → UDP Race Telemetry**

| Setting | Value |
| --- | --- |
| Data Out | On |
| Data Out IP Address | IP of the machine running SimStrategist (`127.0.0.1` if same PC) |
| Data Out IP Port | See per-game defaults below |

Forza Horizon does **not** offer a packet format selector — the format is fixed per game title. (Forza Motorsport does offer "Sled" vs "Dash" format selection; see `forza_mtrspt/` for that.)

---

## Game Versions and Packet Sizes

There is no `packet_format` version field inside Forza Horizon packets. The game version must be inferred from the **packet size** after receiving the first datagram.

| Game | Default Port | Packet Size | Notes |
| --- | --- | --- | --- |
| Forza Horizon 3 | — | — | No UDP telemetry; not supported |
| Forza Horizon 4 | 20044 | 324 bytes | Includes a 12-byte trailing extension beyond the base Dash struct |
| Forza Horizon 5 | 20055 | 323 bytes | Revised layout; one byte shorter than FH4 |

Because both games can be pointed at any port, the listener should accept on a configurable port and detect the game version from the packet size on arrival.

---

## Packet Structure

Both FH4 and FH5 use a superset of the **Forza "Dash" format** — a flat binary struct with little-endian encoding. The packet is divided conceptually into three blocks:

### Block 1 — Sled (motion platform data, bytes 0–231)

This block originates from Forza Motorsport's "Sled" format and is shared across all Forza titles.

| Bytes | Type | Field | Notes |
| --- | --- | --- | --- |
| 0–3 | int32 | IsRaceOn | 1 if race is active, 0 in menus |
| 4–7 | uint32 | TimestampMs | Milliseconds since session start |
| 8–11 | float32 | MaxRPM | Engine redline |
| 12–15 | float32 | IdleRPM | Engine idle speed |
| 16–19 | float32 | CurrentEngineRpm | Current RPM |
| 20–31 | float32 × 3 | AccelerationX/Y/Z | m/s² |
| 32–43 | float32 × 3 | VelocityX/Y/Z | m/s |
| 44–55 | float32 × 3 | AngularVelocityX/Y/Z | rad/s |
| 56–67 | float32 × 3 | Yaw, Pitch, Roll | Radians |
| 68–83 | float32 × 4 | NormalizedSuspensionTravel FL/FR/RL/RR | 0.0–1.0 |
| 84–99 | float32 × 4 | TireSlipRatio FL/FR/RL/RR | |
| 100–115 | float32 × 4 | WheelRotationSpeed FL/FR/RL/RR | rad/s |
| 116–131 | float32 × 4 | WheelOnRumbleStrip FL/FR/RL/RR | |
| 132–147 | float32 × 4 | WheelInPuddleDepth FL/FR/RL/RR | 0.0–1.0 |
| 148–163 | float32 × 4 | SurfaceRumble FL/FR/RL/RR | |
| 164–179 | float32 × 4 | TireSlipAngle FL/FR/RL/RR | |
| 180–195 | float32 × 4 | TireCombinedSlip FL/FR/RL/RR | |
| 196–211 | float32 × 4 | SuspensionTravelMeters FL/FR/RL/RR | |
| 212–215 | int32 | CarOrdinal | Unique car type ID |
| 216–219 | int32 | CarClass | 0=D, 1=C, 2=B, 3=A, 4=S1, 5=S2, 6=X |
| 220–223 | int32 | CarPerformanceIndex | 100–999 |
| 224–227 | int32 | DriveTrainType | 0=FWD, 1=RWD, 2=AWD |
| 228–231 | int32 | NumCylinders | |

### Block 2 — Dash (dashboard data, bytes 232–310)

This block is shared with Forza Motorsport's "Dash" format.

| Bytes | Type | Field | Notes |
| --- | --- | --- | --- |
| 232–243 | float32 × 3 | PositionX/Y/Z | World position (metres) |
| 244–247 | float32 | Speed | m/s — multiply by 3.6 for km/h |
| 248–251 | float32 | Power | Watts |
| 252–255 | float32 | Torque | Nm |
| 256–271 | float32 × 4 | TireTemp FL/FR/RL/RR | Celsius |
| 272–275 | float32 | Boost | Bar |
| 276–279 | float32 | Fuel | 0.0–1.0 (fraction remaining) |
| 280–283 | float32 | DistanceTraveled | Metres |
| 284–287 | float32 | BestLap | Seconds |
| 288–291 | float32 | LastLap | Seconds |
| 292–295 | float32 | CurrentLap | Seconds |
| 296–299 | float32 | CurrentRaceTime | Seconds |
| 300–301 | uint16 | LapNumber | |
| 302 | uint8 | RacePosition | |
| 303 | uint8 | Accel | 0–255 — divide by 255 for 0.0–1.0 |
| 304 | uint8 | Brake | 0–255 — divide by 255 for 0.0–1.0 |
| 305 | uint8 | Clutch | 0–255 |
| 306 | uint8 | HandBrake | 0–255 |
| 307 | uint8 | Gear | 0=reverse, 1=neutral, 2–9=gears 1–8 |
| 308 | int8 | Steer | -127 to 127 — divide by 127 for -1.0–1.0 |
| 309 | int8 | NormalizedDrivingLine | |
| 310 | int8 | NormalizedAIBrakeDifference | |

**Total at this point: 311 bytes** — identical to Forza Motorsport 7's Dash packet.

### Block 3 — Horizon extension (bytes 311–end)

FH4 and FH5 append additional bytes beyond the FM7 struct. The exact layout of these extra bytes is less well-documented and differs between the two titles, which is why packet size is the reliable discriminator.

| Game | Extra bytes | Known content |
| --- | --- | --- |
| FH4 | 13 bytes (311–323) | Additional fields; exact layout requires verification |
| FH5 | 12 bytes (311–322) | Revised layout; 1 byte shorter than FH4 |

---

## Version Detection Strategy

Since there is no version field, the listener should detect which game is connected by examining the first packet received:

```python
VERSION_BY_SIZE = {
    324: 'fh4',
    323: 'fh5',
}

def detect_game(packet: bytes) -> str | None:
    return VERSION_BY_SIZE.get(len(packet))
```

If the packet size does not match any known value, log a warning and skip the packet — it may be from a different Forza title (e.g. Forza Motorsport, which belongs in `forza_mtrspt/`).

---

## Struct Format Strings

### Blocks 1 + 2 combined (bytes 0–310, 311 bytes)

```python
# fmt: <  = little-endian
# Block 1 (Sled):
#   iI                           IsRaceOn, TimestampMs
#   fff                          MaxRPM, IdleRPM, CurrentEngineRPM
#   fff fff fff                  Accel, Velocity, AngularVelocity (XYZ each)
#   fff                          Yaw, Pitch, Roll
#   ffff ffff ffff ffff ffff     Suspension, SlipRatio, WheelSpeed, Rumble, Puddle (×4 wheels each)
#   ffff                         SurfaceRumble ×4
#   ffff ffff                    TireSlipAngle ×4, TireCombinedSlip ×4
#   ffff                         SuspensionTravelMeters ×4
#   iiii                         CarOrdinal, CarClass, CarPerfIndex, DriveTrain, NumCylinders
# Block 2 (Dash):
#   fff                          PositionX/Y/Z
#   ff ff                        Speed, Power, Torque
#   ffff                         TireTemp ×4
#   ff ff ff ff                  Boost, Fuel, DistanceTraveled, BestLap, LastLap, CurrentLap, CurrentRaceTime
#   Hb                           LapNumber (uint16), (gap — see below)
#   BBBBBB b b b                 RacePos, Accel, Brake, Clutch, HandBrake, Gear, Steer, DrivingLine, AIBrake

SLED_DASH_FMT = '<iIffffff ffffffffffffffffffffffffffffffff ffffffffffffffffffffffff iiii fffffffffff fffffffffff H B BBBBBB bbb'
```

> **Note:** The exact format string must be validated by comparing `struct.calcsize()` against the known packet sizes. Use a community reference implementation (e.g. `richstokes/Forza-data-tools` or `austinbaccus/forza-telemetry` on GitHub) as a ground truth before finalising.

---

## Proposed File Structure

Mirrors the `f1/` layout:

```
forza_hrzn/
├── PLAN.md            ← this file
├── __init__.py
├── config.py          ← ports, buffer sizes, version map
├── server.py          ← UdpListener: receives packets, detects game version, calls parser
├── telemetry_state.py ← thread-safe singleton, same interface as f1/telemetry_state.py
```

### `config.py`

```python
UDP_IP         = '0.0.0.0'
FH4_PORT       = 20044
FH5_PORT       = 20055
BUFFER_SIZE    = 1024
TELEMETRY_HZ   = 60   # Forza sends at ~60 Hz (vs F1's 20 Hz)
HISTORY_SECS   = 120
HISTORY_LEN    = TELEMETRY_HZ * HISTORY_SECS  # 7 200 points
```

### `server.py` — key logic

The listener binds to a single port (configurable; default `FH5_PORT`). Game version is determined from the first valid packet.

```python
VERSION_BY_SIZE = {324: 'fh4', 323: 'fh5'}

class ForzaHorizonParser:
    # Shared Sled+Dash struct (311 bytes)
    SLED_DASH_FMT   = '<...'
    SLED_DASH_SIZE  = struct.calcsize(SLED_DASH_FMT)

    @staticmethod
    def parse(packet: bytes, version: str) -> dict | None:
        if len(packet) < ForzaHorizonParser.SLED_DASH_SIZE:
            return None
        d = struct.unpack_from(ForzaHorizonParser.SLED_DASH_FMT, packet)
        return {
            'is_race_on':     d[0],
            'rpm':            d[4],          # CurrentEngineRpm
            'max_rpm':        d[2],
            'speed_kmh':      d[...] * 3.6,  # Speed field is m/s
            'gear':           d[...],        # 0=R, 1=N, 2–9=gears
            'throttle':       d[...] / 255,  # Accel uint8 → 0.0–1.0
            'brake':          d[...] / 255,
            'clutch':         d[...] / 255,
            'steer':          d[...] / 127,  # int8 → -1.0–1.0
            'tyre_temp':      [d[...], d[...], d[...], d[...]],  # FL FR RL RR °C
            'fuel':           d[...],        # 0.0–1.0
            'boost':          d[...],
            'lap_number':     d[...],
            'current_lap':    d[...],
            'last_lap':       d[...],
            'best_lap':       d[...],
            'race_position':  d[...],
            'car_class':      d[...],
            'car_perf_index': d[...],
        }
```

> `d[...]` placeholders must be replaced with the correct unpacked tuple indices once the format string is finalised.

### `telemetry_state.py`

Expose the same public interface as `f1/telemetry_state.py` so `app.py` can treat both identically:

- `state.update(parsed_dict)`
- `state.get_snapshot() → dict`
- `state.get_history_df() → DataFrame`
- `state.connected: bool`
- `state.last_update_time: float`

---

## Integration with `app.py`

Once the listener is implemented, `app.py` needs:

1. A background thread starting `forza_hrzn.server.UdpListener` (alongside the existing F1 and LMU threads).
2. The `/api/telemetry/stream?game=forza_hrzn` SSE branch to pull from `forza_hrzn.telemetry_state.state`.
3. The game dropdown in `telemetry.html` / `strategy.html` to include FH4 and FH5 entries under a new **Forza Horizon** group.

---

## Key Differences from F1

| Aspect | F1 (2018–2024) | Forza Horizon 4/5 |
| --- | --- | --- |
| Format type | Binary UDP, multiple packet IDs | Binary UDP, single packet per frame |
| Version detection | `packet_format` field in header | Packet size |
| Send rate | ~20 Hz | ~60 Hz |
| Packet sizes | 23–28 byte header + variable body | 323–324 bytes total |
| Official spec | Yes (EA/Codemasters forums) | No — community reverse-engineered |
| Tyre temperatures | Yes | Yes |
| Fuel | Yes | Yes (fraction, not kg) |
| Weather / session data | Yes | No |
| Pit status / lap invalid | Yes | No |
| Car class / PI | No | Yes |

---

## References

- Community packet structure discussion: `forums.forza.net/t/data-out-telemetry-variables-and-structure/535984`
- `richstokes/Forza-data-tools` — Python tools using the reverse-engineered struct
- `austinbaccus/forza-telemetry` — C# implementation with documented field list
- Official Forza Motorsport Data Out doc (Motorsport only, but Sled/Dash blocks are shared): `support.forzamotorsport.net/hc/en-us/articles/21742934024211`
