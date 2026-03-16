const WEATHER_DESC = {
    0: 'Clear', 1: 'Light Cloud', 2: 'Overcast',
    3: 'Light Rain', 4: 'Heavy Rain', 5: 'Storm'
};

const TYRE_LABELS = ['FL', 'FR', 'RL', 'RR'];

function fmtMs(ms) {
    if (!ms) return '--';
    const totalSec = Math.floor(ms / 1000);
    const min = Math.floor(totalSec / 60);
    const sec = totalSec % 60;
    const millis = ms % 1000;
    return `${min}:${String(sec).padStart(2,'0')}.${String(millis).padStart(3,'0')}`;
}

function buildRecommendations(data) {
    const t = data.telemetry;
    const lap = data.lap_data;
    const sess = data.session;
    const connected = data.connected;

    const items = [];

    if (!connected) {
        items.push({ severity: 'alert', msg: 'No telemetry data — ensure the F1 game is running and UDP output is enabled on port 20777.' });
        return items;
    }

    const weather = sess.weather || 0;
    if (weather >= 3) {
        items.push({ severity: 'warning', msg: `Rain conditions detected (${WEATHER_DESC[weather]}) — consider switching to intermediate or wet tyres.` });
    }

    const tyres = t.tyres_surface_temp || [0,0,0,0];
    tyres.forEach((temp, i) => {
        if (temp > 110) {
            items.push({ severity: 'warning', msg: `Tyre overheating: ${TYRE_LABELS[i]} at ${temp}°C — ease off exit throttle to cool tyres.` });
        } else if (temp > 0 && temp < 70) {
            items.push({ severity: 'info', msg: `Tyre too cold: ${TYRE_LABELS[i]} at ${temp}°C — push harder through corners to build tyre temperature.` });
        }
    });

    const penalties = lap.penalties || 0;
    if (penalties > 0) {
        items.push({ severity: 'alert', msg: `You have ${penalties} second${penalties !== 1 ? 's' : ''} of time penalties to serve.` });
    }

    if (lap.current_lap_invalid) {
        items.push({ severity: 'info', msg: 'Current lap is invalid — focus on posting a clean next lap.' });
    }

    const curLap = lap.current_lap_time || 0;
    const bestLap = lap.best_lap_time || 0;
    if (bestLap > 0 && curLap > bestLap * 1.05) {
        items.push({ severity: 'info', msg: `Lap time is ${fmtMs(curLap)} — currently ${((curLap/bestLap - 1)*100).toFixed(1)}% off best (${fmtMs(bestLap)}). Review braking points.` });
    }

    const pitStatus = lap.pit_status || 0;
    if (pitStatus === 1) {
        items.push({ severity: 'info', msg: 'Currently entering pit lane.' });
    } else if (pitStatus === 2) {
        items.push({ severity: 'info', msg: 'Currently in the pit area.' });
    }

    const engineTemp = t.engine_temp || 0;
    if (engineTemp > 120) {
        items.push({ severity: 'warning', msg: `Engine temperature is high (${engineTemp}°C) — consider reducing engine mode.` });
    }

    if (items.length === 0) {
        items.push({ severity: 'info', msg: 'All systems nominal — maintain current pace.' });
    }

    return items;
}

function severityClass(s) {
    if (s === 'alert') return 'badge-alert';
    if (s === 'warning') return 'badge-warning';
    return 'badge-info';
}

function renderRecommendations(items) {
    const list = document.getElementById('recommendations-list');
    list.innerHTML = items.map(item => `
        <div class="strategy-card mb-3 severity-${item.severity}">
            <span class="severity-badge ${severityClass(item.severity)}">${item.severity.toUpperCase()}</span>
            <span class="ms-3 text-white">${item.msg}</span>
        </div>
    `).join('');
}

async function poll() {
    try {
        const resp = await fetch('/api/telemetry');
        const data = await resp.json();
        const sess = data.session;
        const lap = data.lap_data;

        document.getElementById('s-position').textContent = lap.car_position || '--';
        document.getElementById('s-lap').textContent = lap.current_lap || '--';
        document.getElementById('s-total-laps').textContent = sess.total_laps || '--';
        document.getElementById('s-track-temp').textContent = (sess.track_temperature || '--') + '°C';
        document.getElementById('s-air-temp').textContent = (sess.air_temperature || '--') + '°C';
        document.getElementById('s-weather').textContent = WEATHER_DESC[sess.weather] || '--';

        renderRecommendations(buildRecommendations(data));
    } catch(e) {
        renderRecommendations([{ severity: 'alert', msg: 'Could not reach telemetry API.' }]);
    }
}

poll();
setInterval(poll, 1000);
