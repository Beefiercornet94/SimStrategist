# SimStrategist


## Description

SimStrategist is a tool that displays and analyses live in-game telemetry from various racing simulators.


### Compatible Simulators:
- F1 (2022->)
- Le Mans Ultimate


## Usage

### Activation (F1)

### Installation (LMU)
 

### UDP Listener Startup:
- "cd f1" - This will change directory to the "F1" folder
- "python3 server.py" - This will start a UDP listener on port 20777


## External Code Used:

### Telemetry Data:
- Parsing code for the F1 games taken from Harmitx7's F1-TELEMETRY-Dashboard at "https://github.com/Harmitx7/F1-TELEMETRY-DASHBOARD"
- JSON Module for LMU taken from the community forums at "https://community.lemansultimate.com/index.php?threads/telemetry-socket-%E2%80%93-json-telemetry-plugin.8229/"

### Website Application Design:
- Login/Logout/Register taken from implementation in CS50x's Finance Problem Set
- "@login_required" and "apology" / "apology.html" in "helpers.py" taken from CS50x's Finance Problem Set
