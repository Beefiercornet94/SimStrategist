// ── Constants ──────────────────────────────────────────────────────────────────

const WEATHER_DESC = {
    0: 'Clear', 1: 'Light Cloud', 2: 'Overcast',
    3: 'Light Rain', 4: 'Heavy Rain', 5: 'Storm'
};

const WEATHER_ICON = {
    0: '☀️', 1: '⛅', 2: '☁️', 3: '🌦️', 4: '🌧️', 5: '⛈️'
};

const TYRE_LABELS = ['FL', 'FR', 'RL', 'RR'];

const VISUAL_COMPOUND = {
    16: 'Soft', 17: 'Medium', 18: 'Hard', 7: 'Intermediate', 8: 'Wet'
};

const COMPOUND_COLOUR = {
    Soft: '#e8002d', Medium: '#ffd000', Hard: '#f0f0ec',
    Intermediate: '#43b02a', Wet: '#0067ff', Unknown: '#888888'
};

// ── State ──────────────────────────────────────────────────────────────────────

let activeGame = 'f1';
let analysisRunning = false;

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtMs(ms) {
    if (!ms) return '--:--.---';
    const m  = Math.floor(ms / 60000);
    const s  = Math.floor((ms % 60000) / 1000);
    const mi = ms % 1000;
    return `${m}:${String(s).padStart(2,'0')}.${String(mi).padStart(3,'0')}`;
}

function fmtSec(s) {
    if (!s) return '--:--.---';
    const m  = Math.floor(s / 60);
    const sc = Math.floor(s % 60);
    const mi = Math.round((s % 1) * 1000);
    return `${m}:${String(sc).padStart(2,'0')}.${String(mi).padStart(3,'0')}`;
}

function fmtDeltaSeconds(sec) {
    const abs = Math.abs(sec);
    const m   = Math.floor(abs / 60);
    const s   = abs % 60;
    const sign = sec < 0 ? '-' : '+';
    return m > 0
        ? `${sign}${m}:${String(s).padStart(2,'0')}`
        : `${sign}${s}s`;
}

// ── Session summary ────────────────────────────────────────────────────────────

function updateSessionSummary(data) {
    const t    = data.telemetry;
    const lap  = data.lap_data;
    const sess = data.session;
    const isF1 = activeGame === 'f1';

    // Badge
    const badge = document.getElementById('conn-badge');
    badge.textContent = data.connected ? 'Connected' : 'Disconnected';
    badge.className   = 'badge ' + (data.connected ? 'bg-success' : 'bg-danger');

    document.getElementById('s-position').textContent = lap.car_position || '--';
    document.getElementById('s-lap').textContent      = lap.current_lap  || '--';

    if (isF1) {
        document.getElementById('s-extra-label').textContent = 'Total Laps';
        document.getElementById('s-extra').textContent = sess.total_laps || '--';
        document.getElementById('s-wx-label').textContent = 'Weather';
        document.getElementById('s-weather').textContent =
            (WEATHER_ICON[sess.weather] || '') + ' ' + (WEATHER_DESC[sess.weather] || '--');
        document.getElementById('s-track-temp').textContent =
            (sess.track_temperature != null ? sess.track_temperature : '--') + '°C';
        document.getElementById('s-air-temp').textContent =
            (sess.air_temperature != null ? sess.air_temperature : '--') + '°C';

        // Tyre / fuel row (F1 only)
        document.getElementById('tyre-fuel-row').style.display = '';
        const vcId = t.tyre_visual_compound;
        const compound = VISUAL_COMPOUND[vcId] || '--';
        const compColour = COMPOUND_COLOUR[compound] || '#888';
        document.getElementById('s-compound').innerHTML =
            `<span style="color:${compColour}; font-weight:700;">${compound}</span>`;
        document.getElementById('s-tyre-age').textContent =
            (t.tyre_age_laps != null ? t.tyre_age_laps : '--') + ' laps';
        document.getElementById('s-fuel-label').textContent = 'Fuel / Laps Left';
        document.getElementById('s-fuel').textContent =
            t.fuel_in_tank != null
                ? `${t.fuel_in_tank.toFixed(1)} kg / ~${(t.fuel_remaining_laps || 0).toFixed(1)} laps`
                : '--';
        document.getElementById('s-best-lap').textContent = fmtMs(lap.best_lap_time);

    } else {
        document.getElementById('s-extra-label').textContent = 'Track';
        document.getElementById('s-extra').textContent = sess.track_name || '--';
        document.getElementById('s-wx-label').textContent = 'Flag';
        document.getElementById('s-weather').textContent = (sess.flag || '--').toUpperCase();
        document.getElementById('s-track-temp').textContent =
            (sess.track_temp != null ? sess.track_temp : '--') + '°C';
        document.getElementById('s-air-temp').textContent =
            (sess.ambient_temp != null ? sess.ambient_temp : '--') + '°C';

        // Show fuel, hide tyre compound/age for LMU
        document.getElementById('tyre-fuel-row').style.display = '';
        document.getElementById('s-compound').textContent = '--';
        document.getElementById('s-tyre-age').textContent = '--';
        document.getElementById('s-fuel-label').textContent = 'Fuel Remaining';
        document.getElementById('s-fuel').textContent =
            t.fuel != null ? `${t.fuel.toFixed(1)} kg` : '--';
        document.getElementById('s-best-lap').textContent = fmtSec(lap.best_lap_time);
    }
}

// ── Weather history ────────────────────────────────────────────────────────────

async function refreshWeatherHistory() {
    try {
        const resp = await fetch(`/api/weather/history?game=${activeGame}`);
        const entries = await resp.json();
        renderWeatherHistory(entries);
    } catch (_) {}
}

function renderWeatherHistory(entries) {
    const isF1     = activeGame === 'f1';
    const container = document.getElementById('wx-history-body');
    const title     = document.getElementById('wx-section-title');
    title.textContent = isF1 ? 'Weather History' : 'Conditions History';

    if (!entries || entries.length === 0) {
        container.innerHTML =
            '<p class="text-secondary mb-0" style="font-size:.85rem;">' +
            'Waiting for data — conditions are recorded every time weather or ' +
            'temperature changes by 2°C or more.</p>';
        return;
    }

    // Build a table
    let html = `
        <div class="table-responsive">
        <table class="table table-dark table-sm mb-0" style="font-size:.85rem;">
            <thead>
                <tr>
                    <th>Lap</th>
                    ${isF1 ? '<th>Condition</th>' : '<th>Flag</th>'}
                    <th>Track Temp</th>
                    <th>Air Temp</th>
                    <th>Change</th>
                </tr>
            </thead>
            <tbody>`;

    entries.slice().reverse().forEach((e, i) => {
        const prev    = entries[entries.length - 2 - i]; // compare against previous row
        const isLatest = i === 0;
        const rowClass = isLatest ? 'table-active' : '';
        const cond     = isF1
            ? `${WEATHER_ICON[e.weather] || ''} ${e.weather_desc}`
            : (e.weather >= 3 ? '🌧️ Rain' : '☀️ Dry');

        let change = '';
        if (prev) {
            const trackDiff = (e.track_temp - prev.track_temp).toFixed(1);
            const airDiff   = (e.air_temp   - prev.air_temp  ).toFixed(1);
            const parts = [];
            if (isF1 && e.weather !== prev.weather)
                parts.push(`${prev.weather_desc} → ${e.weather_desc}`);
            if (Math.abs(e.track_temp - prev.track_temp) >= 2)
                parts.push(`Track ${trackDiff > 0 ? '+' : ''}${trackDiff}°C`);
            if (Math.abs(e.air_temp - prev.air_temp) >= 2)
                parts.push(`Air ${airDiff > 0 ? '+' : ''}${airDiff}°C`);
            change = parts.join(', ');
        } else {
            change = '<span class="text-secondary">Session start</span>';
        }

        html += `
            <tr class="${rowClass}">
                <td>${e.lap}</td>
                <td>${cond}</td>
                <td>${e.track_temp}°C</td>
                <td>${e.air_temp}°C</td>
                <td>${change}</td>
            </tr>`;
    });

    html += '</tbody></table></div>';
    container.innerHTML = html;
    document.getElementById('wx-update-time').textContent =
        'Updated ' + new Date().toLocaleTimeString();
}

// ── Live recommendations ───────────────────────────────────────────────────────

function buildRecommendations(data) {
    const t         = data.telemetry;
    const lap       = data.lap_data;
    const sess      = data.session;
    const connected = data.connected;
    const isF1      = activeGame === 'f1';
    const items     = [];

    if (!connected) {
        items.push({ severity: 'alert', msg: 'No telemetry data — ensure the game is running and output is enabled.' });
        return items;
    }

    if (isF1) {
        const weather = sess.weather || 0;
        if (weather >= 3) {
            items.push({ severity: 'warning', msg: `Rain conditions (${WEATHER_DESC[weather]}) — consider switching to intermediate or wet tyres.` });
        }

        const tyres = t.tyres_surface_temp || [0, 0, 0, 0];
        tyres.forEach((temp, i) => {
            if (temp > 110)
                items.push({ severity: 'warning', msg: `Tyre overheating: ${TYRE_LABELS[i]} at ${temp}°C — ease off exit throttle.` });
            else if (temp > 0 && temp < 70)
                items.push({ severity: 'info', msg: `Tyre too cold: ${TYRE_LABELS[i]} at ${temp}°C — push harder to build temperature.` });
        });

        const tWear = t.tyre_wear || [0, 0, 0, 0];
        tWear.forEach((wear, i) => {
            if (wear > 75)
                items.push({ severity: 'warning', msg: `High tyre wear: ${TYRE_LABELS[i]} at ${wear.toFixed(0)}% — consider an early pit stop.` });
        });

        const fuelLaps = t.fuel_remaining_laps || 0;
        const lapsLeft = (sess.total_laps || 0) - (lap.current_lap || 0);
        if (fuelLaps > 0 && lapsLeft > 0 && fuelLaps < lapsLeft) {
            items.push({ severity: 'alert', msg: `Fuel will run out in ~${fuelLaps.toFixed(0)} laps but ${lapsLeft} remain — reduce fuel mix or plan an extra stop.` });
        }

        if ((lap.penalties || 0) > 0)
            items.push({ severity: 'alert', msg: `${lap.penalties}s of time penalties to serve.` });

        if (lap.current_lap_invalid)
            items.push({ severity: 'info', msg: 'Current lap is invalid — focus on a clean next lap.' });

        const engineTemp = t.engine_temp || 0;
        if (engineTemp > 120)
            items.push({ severity: 'warning', msg: `Engine temperature high (${engineTemp}°C) — reduce engine mode.` });

    } else {
        // LMU
        const flag = (sess.flag || '').toLowerCase();
        if (flag === 'yellow')
            items.push({ severity: 'warning', msg: 'Yellow flag — maintain position and do not overtake.' });
        if (flag === 'red')
            items.push({ severity: 'alert', msg: 'Red flag — stop the car safely and await instructions.' });

        const fuel = t.fuel || 0;
        if (fuel > 0 && fuel < 5)
            items.push({ severity: 'alert', msg: `Fuel critically low (${fuel.toFixed(1)} kg) — pit immediately or manage pace.` });

        const water = t.engine_water_temp || 0;
        if (water > 120)
            items.push({ severity: 'warning', msg: `Water temperature high (${water.toFixed(0)}°C) — reduce engine power.` });

        const oil = t.engine_oil_temp || 0;
        if (oil > 130)
            items.push({ severity: 'warning', msg: `Oil temperature high (${oil.toFixed(0)}°C) — check engine settings.` });
    }

    // Shared
    const curLap  = lap.current_lap_time || 0;
    const bestLap = lap.best_lap_time    || 0;
    if (bestLap > 0 && curLap > bestLap * 1.05) {
        const pct   = ((curLap / bestLap - 1) * 100).toFixed(1);
        const curFmt  = isF1 ? fmtMs(curLap)  : fmtSec(curLap);
        const bestFmt = isF1 ? fmtMs(bestLap) : fmtSec(bestLap);
        items.push({ severity: 'info', msg: `Lap time ${curFmt} — ${pct}% off best (${bestFmt}). Review braking points.` });
    }

    if ((lap.pit_status || 0) === 1)
        items.push({ severity: 'info', msg: 'Entering pit lane.' });
    else if ((lap.pit_status || 0) === 2)
        items.push({ severity: 'info', msg: 'In the pit area.' });

    if (items.length === 0)
        items.push({ severity: 'info', msg: 'All systems nominal — maintain current pace.' });

    return items;
}

function severityClass(s) {
    if (s === 'alert')   return 'badge-alert';
    if (s === 'warning') return 'badge-warning';
    return 'badge-info';
}

function renderRecommendations(items) {
    document.getElementById('recommendations-list').innerHTML = items.map(item => `
        <div class="strategy-card mb-3 severity-${item.severity}">
            <span class="severity-badge ${severityClass(item.severity)}">${item.severity.toUpperCase()}</span>
            <span class="ms-3 text-white">${item.msg}</span>
        </div>
    `).join('');
}

// ── AI strategy ────────────────────────────────────────────────────────────────

function renderAiStrategy(result) {
    const grid   = document.getElementById('ai-strategy-grid');
    const status = document.getElementById('ai-status');

    if (result.error) {
        status.textContent = '⚠ ' + result.error;
        status.style.display = '';
        grid.style.display = 'none !important';
        return;
    }

    status.style.display = 'none';

    const strats = [
        { key: 'standard', label: 'Standard', accent: '#00d2be' },
        { key: 'push',     label: 'Push',     accent: '#00ff87' },
        { key: 'save',     label: 'Save',      accent: '#ffa502' },
    ];

    grid.innerHTML = strats.map(({ key, label, accent }) => {
        const s = result[key];
        if (!s) return '';

        const deltaRaw = s.delta_seconds || 0;
        let deltaHtml = '';
        if (deltaRaw === 0) {
            deltaHtml = '<span class="text-secondary">Reference</span>';
        } else if (deltaRaw < 0) {
            deltaHtml = `<span style="color:#00ff87; font-weight:700;">${fmtDeltaSeconds(deltaRaw)} faster</span>`;
        } else {
            deltaHtml = `<span style="color:#ff4757; font-weight:700;">${fmtDeltaSeconds(deltaRaw)} slower</span>`;
        }

        const stintRows = (s.stint_plan || []).map(stint => {
            const col = stint.colour || COMPOUND_COLOUR[stint.compound] || '#888';
            return `
                <tr>
                    <td>
                        <span style="display:inline-block; width:10px; height:10px;
                            background:${col}; border-radius:50%; margin-right:6px;"></span>
                        <strong>${stint.compound}</strong>
                    </td>
                    <td class="text-center">${stint.laps} laps</td>
                    <td class="text-secondary" style="font-size:.8rem;">${stint.notes || ''}</td>
                </tr>`;
        }).join('');

        return `
            <div class="col-md-4">
                <div class="dash-card h-100" style="border-top: 3px solid ${accent};">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="fw-bold" style="color:${accent}; font-size:1rem;">${s.name || label}</span>
                        <span class="text-secondary" style="font-size:.8rem;">${s.stops} stop${s.stops !== 1 ? 's' : ''}</span>
                    </div>

                    <div class="mb-2" style="font-size:.85rem; color:#ccc;">${s.summary || ''}</div>

                    <table class="table table-dark table-sm mb-2" style="font-size:.82rem;">
                        <thead>
                            <tr>
                                <th>Compound</th>
                                <th class="text-center">Duration</th>
                                <th>Notes</th>
                            </tr>
                        </thead>
                        <tbody>${stintRows}</tbody>
                    </table>

                    <div class="d-flex justify-content-between align-items-center mt-auto pt-2"
                         style="border-top:1px solid #333;">
                        <span class="text-secondary" style="font-size:.8rem;">
                            Est. time: <span class="text-white">${s.est_total_time || '--'}</span>
                        </span>
                        <span style="font-size:.85rem;">${deltaHtml}</span>
                    </div>
                </div>
            </div>`;
    }).join('');

    grid.style.cssText = '';   // clear the !important hide
    grid.style.display = 'flex';
    grid.classList.add('row', 'g-3');
}

async function runAnalysis() {
    if (analysisRunning) return;
    analysisRunning = true;

    const btn    = document.getElementById('btn-analyse');
    const status = document.getElementById('ai-status');
    const grid   = document.getElementById('ai-strategy-grid');

    btn.disabled     = true;
    btn.textContent  = 'Analysing…';
    status.textContent = '⏳ Sending telemetry to Claude for analysis…';
    status.style.display = '';
    grid.style.display = 'none';

    try {
        const resp = await fetch('/api/strategy/ai', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ game: activeGame }),
        });
        const result = await resp.json();
        renderAiStrategy(result);
    } catch (e) {
        status.textContent = '⚠ Failed to reach the strategy API.';
        status.style.display = '';
    } finally {
        btn.disabled    = false;
        btn.textContent = 'Analyse Strategy';
        analysisRunning = false;
    }
}

// ── Polling ────────────────────────────────────────────────────────────────────

async function poll() {
    try {
        const resp = await fetch(`/api/telemetry${activeGame === 'lmu' ? '?game=lmu' : ''}`);
        const data = await resp.json();
        updateSessionSummary(data);
        renderRecommendations(buildRecommendations(data));
    } catch (_) {
        renderRecommendations([{ severity: 'alert', msg: 'Could not reach telemetry API.' }]);
    }
}

// ── Game toggle ────────────────────────────────────────────────────────────────

document.querySelectorAll('#game-toggle button').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('#game-toggle button').forEach(b => {
            b.classList.replace('btn-primary', 'btn-outline-primary');
            b.classList.remove('active');
        });
        btn.classList.replace('btn-outline-primary', 'btn-primary');
        btn.classList.add('active');
        activeGame = btn.dataset.game;

        // Reset AI panel when switching game
        document.getElementById('ai-strategy-grid').style.display = 'none';
        document.getElementById('ai-status').style.display = 'none';

        refreshWeatherHistory();
    });
});

document.getElementById('btn-analyse').addEventListener('click', runAnalysis);

// ── Boot ───────────────────────────────────────────────────────────────────────

poll();
refreshWeatherHistory();
setInterval(poll, 1000);
setInterval(refreshWeatherHistory, 15000);
