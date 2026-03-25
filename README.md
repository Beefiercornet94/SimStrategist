# SimStrategist

## Description

SimStrategist is a tool that displays and analyses live in-game telemetry from various racing simulators.

### Compatible Simulators

| Generation | Games | Platforms |
| --- | --- | --- |
| Gen 5 | F1 2022, F1 2023, F1 2024 | All |
| Gen 4 | F1 2021 | All |
| Gen 3 | F1 2020 | All |
| Gen 2 | F1 2018, F1 2019 | All |
| ~~Gen 1~~ | ~~F1 2017~~ | — Not supported |
| — | Le Mans Ultimate | PC |

## Features

- **Live telemetry dashboard** — gear, speed, RPM shift lights, DRS, engine temps, tyre temps
- **Driver inputs panel** — throttle, brake, clutch, and steering displayed in real time; toggle between bar view and scrolling graph view
- **Lap times** — current, last, best, sector 1, and sector 2 times
- **Strategy co-pilot** — AI-powered pit strategy recommendations using live tyre, fuel, and weather data
- **Weather history** — records track and air temperature samples throughout a session
- **Telemetry recording & replay** — capture a session to a `.f1rec` file and replay it later for development

---

## Usage

### Connecting an F1 Game (2018 – 2024)

SimStrategist auto-detects the game version from each packet, so no manual version configuration is needed on the SimStrategist side. The steps below apply to all supported generations.

1. In the F1 game, go to **Settings → Telemetry Settings**.
2. Set **UDP Telemetry** to `On`.
3. Set **UDP Broadcast Mode** to `Off`.
4. Set **UDP IP Address** to the IP of the machine running SimStrategist:
    - Use `127.0.0.1` if running on the same PC.
    - Use the machine's local IP address if running SimStrategist on a separate device.
5. Set **UDP Port** to `20777`.
6. Set **UDP Send Rate** to `20Hz` (recommended).
7. Set **UDP Format** to match your game year — see the table below.
8. In the SimStrategist web app, use the **game dropdown** (top of the Telemetry or Strategy page) to select your game.
9. Start the telemetry listener:

```bash
python3 f1/server.py
```

> The listener receives data on **UDP port 20777**. Make sure your firewall allows this port if the game runs on a different machine.

#### UDP Format setting by generation

| Generation | Games | Set UDP Format to |
| --- | --- | --- |
| Gen 5 | F1 2022, F1 2023, F1 2024 | Match the game year (e.g. `2024`) |
| Gen 4 | F1 2021 | `2021` |
| Gen 3 | F1 2020 | `2020` |
| Gen 2 | F1 2018, F1 2019 | `2019` or `2018` |

> **Newer games only:** F1 2022–2024 include a *UDP Format* setting that lets you downgrade the output to an older spec. Always set it to match your actual game year — do not downgrade unless you have a specific reason to.

---

### Connecting Le Mans Ultimate

1. Download and install the **Ultimate Telemetry Socket – JSON Telemetry Plugin** from the Le Mans Ultimate community forums.
2. Place the plugin DLL in your LMU `Plugins` folder.
3. In the plugin configuration file, set the port to `5100` and the output host as below:
    - Use `127.0.0.1` as the output hostif on the same PC
    - Find the IP address of the PC running it if you are using a seperate device
4. Start Le Mans Ultimate — the plugin will begin sending telemetry automatically.
5. Start the telemetry listener:

```bash
python3 lmu/server.py
```

> The listener accepts connections on **TCP port 5100** by default. To use UDP instead, run `python3 lmu/server.py --udp`. To change the port, add `--port <number>`.

---

### Starting the Web App

```bash
python3 app.py
```

The app should be automatically opened in a new tab

## External Code Used

### Telemetry Data

- Parsing code for the F1 games taken from Harmitx7's F1-TELEMETRY-Dashboard at "github.com/Harmitx7/F1-TELEMETRY-DASHBOARD"
- JSON Module for LMU taken from the community forums at "community.lemansultimate.com/index.php?threads/telemetry-socket-%E2%80%93-json-telemetry-plugin.8229/"

### From various CS50 problem sets

- `Login` flask route
- `login.html`
- `Logout` flask route
- `Register` flask route
- `register.html`
- `apology.html`
- `apology()` function

 (CSS / JavaScript added/removed for aesthetic purposes)

## About me

This is my first GitHub publication, so apologies for any badly-written code and/or unhelpful comments!

Claude AI module inside Visual Studio Code used.
