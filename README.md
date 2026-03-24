# SimStrategist

## Description

SimStrategist is a tool that displays and analyses live in-game telemetry from various racing simulators.

### Compatible Simulators

- F1 (2022 / 2023 / 2024)
- Le Mans Ultimate

## Features

- **Live telemetry dashboard** — gear, speed, RPM shift lights, DRS, engine temps, tyre temps
- **Driver inputs panel** — throttle, brake, clutch, and steering displayed in real time; toggle between bar view and scrolling graph view
- **Lap times** — current, last, best, sector 1, and sector 2 times
- **Strategy co-pilot** — AI-powered pit strategy recommendations using live tyre, fuel, and weather data
- **Weather history** — records track and air temperature samples throughout a session
- **Telemetry recording & replay** — capture a session to a `.f1rec` file and replay it later for development

---

## Usage

### Connecting F1 (2022 / 2023 / 2024)

1. In the F1 game, go to **Settings → Telemetry Settings**.
2. Set **UDP Telemetry** to `On`.
3. Set **UDP Broadcast Mode** to `Off`.
4. Set **UDP IP Address** to the IP of the machine running SimStrategist:
    - Use `127.0.0.1` if on the same PC
    - Find the IP address of the PC running it if you are using a seperate device
5. Set **UDP Port** to `20777`.
6. Set **UDP Send Rate** to `20Hz` (recommended).
7. Set **UDP Format** to match your game year (e.g. `2023`).
8. Start the telemetry listener:

```bash
python3 f1/server.py
```

> The listener receives data on **UDP port 20777**. Make sure your firewall allows this port if the game runs on a different machine.

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

Then open your browser and navigate to `http://127.0.0.1:5000`.

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
