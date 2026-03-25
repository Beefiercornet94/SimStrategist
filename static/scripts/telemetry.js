// ---------- constants ----------
const F1_SESSION_TYPES = {
    0:'Unknown', 1:'Practice 1', 2:'Practice 2', 3:'Practice 3',
    4:'Short Practice', 5:'Qualifying 1', 6:'Qualifying 2', 7:'Qualifying 3',
    8:'Short Qualifying', 9:'One-Shot Qualifying', 10:'Race', 11:'Race 2',
    12:'Race 3', 13:'Time Trial'
};
// Canonical WEC/LMU class colour map.
// Keys are lower-cased, spaces/hyphens stripped versions of what the plugin sends.
const LMU_CLASS_COLORS = {
    'hy':         '#d4a017',  // Hypercar — ACO gold
    'hypercar':   '#d4a017',
    'lmh':        '#d4a017',  // Le Mans Hypercar spec
    'lmdh':       '#d4a017',  // Le Mans Daytona H spec
    'lmp2':       '#0057b8',  // LMP2 — WEC blue
    'lmp3':       '#ff6d00',  // LMP3 — orange
    'lmgt3':      '#00a651',  // LMGT3 — ACO green
    'gt3':        '#00a651',
    'gte':        '#00c87a',  // GTE Pro/Am (legacy class)
    'gtepro':     '#00c87a',
    'gteam':      '#00c87a',
};

const LMU_CLASS_LABELS = {
    'hy': 'HY', 'hypercar': 'HY', 'lmh': 'HY', 'lmdh': 'HY',
    'lmp2': 'LMP2', 'lmp3': 'LMP3',
    'lmgt3': 'LMGT3', 'gt3': 'LMGT3',
    'gte': 'GTE', 'gtepro': 'GTE Pro', 'gteam': 'GTE Am',
};

function normClassKey(raw) {
    return (raw || '').toLowerCase().replace(/[\s\-_]/g, '');
}

// ---------- class ring ----------
const _classRing    = document.getElementById('class-ring');
const _classLabel   = document.getElementById('class-ring-label');
const _wheelCenter  = document.getElementById('wheel-center-card');

function updateClassRing(vehicleClass) {
    const key   = normClassKey(vehicleClass);
    const color = LMU_CLASS_COLORS[key];
    const label = LMU_CLASS_LABELS[key] || (vehicleClass || '').toUpperCase() || '--';

    if (color) {
        // Build a slightly transparent version for the border glow
        const hex = color.replace('#', '');
        const r = parseInt(hex.slice(0,2), 16);
        const g = parseInt(hex.slice(2,4), 16);
        const b = parseInt(hex.slice(4,6), 16);
        const alpha = `rgba(${r},${g},${b},0.35)`;

        _wheelCenter.style.setProperty('--lmu-class-color', color);
        _wheelCenter.style.setProperty('--lmu-class-color-alpha', alpha);
        _wheelCenter.classList.add('wheel-center-class-glow');
    } else {
        _wheelCenter.style.removeProperty('--lmu-class-color');
        _wheelCenter.style.removeProperty('--lmu-class-color-alpha');
        _wheelCenter.classList.remove('wheel-center-class-glow');
    }
    _classLabel.textContent = label;
}

function showClassRing(show) {
    _classRing.style.display = show ? '' : 'none';
    if (!show) {
        _wheelCenter.classList.remove('wheel-center-class-glow');
        _wheelCenter.style.removeProperty('--lmu-class-color');
        _wheelCenter.style.removeProperty('--lmu-class-color-alpha');
    }
}


// ---------- state ----------
let activeGame = 'f1-2024';

function gameFamily(g) { return g.startsWith('f1') ? 'f1' : g; }
let es = null;        // active EventSource
let isRecording = false;
let noSignalModal = null;

function getNoSignalModal() {
    if (!noSignalModal) noSignalModal = new bootstrap.Modal(document.getElementById('no-signal-modal'));
    return noSignalModal;
}

function showNoSignal() {
    const m = document.getElementById('no-signal-modal');
    if (!m.classList.contains('show')) getNoSignalModal().show();
}

function hideNoSignal() {
    const m = document.getElementById('no-signal-modal');
    if (m.classList.contains('show')) getNoSignalModal().hide();
}

// ---------- formatters ----------
function fmtMs(ms) {
    if (!ms) return '--:--.---';
    const min   = Math.floor(ms / 60000);
    const sec   = Math.floor((ms % 60000) / 1000);
    const millis = ms % 1000;
    return `${min}:${String(sec).padStart(2,'0')}.${String(millis).padStart(3,'0')}`;
}

function fmtSec(s) {
    if (!s) return '--:--.---';
    const min    = Math.floor(s / 60);
    const sec    = Math.floor(s % 60);
    const millis = Math.round((s % 1) * 1000);
    return `${min}:${String(sec).padStart(2,'0')}.${String(millis).padStart(3,'0')}`;
}

function fmtSectorMs(ms) { return ms ? (ms / 1000).toFixed(3) + 's' : '--'; }
function fmtSectorSec(s)  { return s  ? s.toFixed(3) + 's' : '--'; }

function tyreColorClass(temp) {
    if (!temp) return '';
    if (temp < 70)  return 'tyre-cold';
    if (temp <= 100) return 'tyre-good';
    if (temp <= 110) return 'tyre-warm';
    return 'tyre-hot';
}

function gearLabel(g) {
    if (g === -1 || g === '-1') return 'R';
    if (g === 0  || g === '0')  return 'N';
    return String(g);
}

// ---------- DOM update ----------
function render(data) {
    const t       = data.telemetry;
    const lap     = data.lap_data;
    const sess    = data.session;
    const isF1    = gameFamily(activeGame) === 'f1';

    // Connection badge
    const badge = document.getElementById('conn-badge');
    badge.textContent = data.connected ? 'Connected' : 'Disconnected';
    badge.className   = 'badge ' + (data.connected ? 'bg-success' : 'bg-danger');

    // Top bar
    document.getElementById('t-position').textContent = lap.car_position || '--';
    document.getElementById('t-lap').textContent      = lap.current_lap  || '--';

    if (isF1) {
        document.getElementById('label-extra').textContent = 'Total Laps';
        document.getElementById('t-extra').textContent     = sess.total_laps || '--';
        document.getElementById('t-session-type').textContent =
            F1_SESSION_TYPES[sess.session_type] ?? '--';
    } else {
        document.getElementById('label-extra').textContent = 'Track';
        document.getElementById('t-extra').textContent     = sess.track_name || '--';
        document.getElementById('t-session-type').textContent = sess.session_type || '--';
    }

    // Speed & Gear
    document.getElementById('t-speed').textContent = isF1
        ? (t.speed || 0)
        : Math.round((t.speed || 0) * 3.6);   // LMU gives m/s
    document.getElementById('t-gear').textContent = gearLabel(t.gear);

    // RPM bar — F1 uses rev_lights_percent; LMU we approximate from raw rpm
    const rpmPct = isF1
        ? Math.min(t.rev_lights_percent || 0, 100)
        : Math.min(((t.rpm || 0) / 12000) * 100, 100);
    document.getElementById('t-rpm-bar').style.width = rpmPct + '%';
    document.getElementById('t-rpm-val').textContent = (t.rpm || 0).toLocaleString();

    // DRS (F1) / Fuel (LMU)
    const drsEl = document.getElementById('t-drs-fuel');
    if (isF1) {
        drsEl.textContent  = t.drs ? 'ON' : 'OFF';
        drsEl.style.color  = t.drs ? '#00ff87' : '#888';
    } else {
        drsEl.textContent = (t.fuel != null) ? t.fuel.toFixed(1) + ' kg' : '--';
        drsEl.style.color = '#fff';
    }

    // Pedal inputs
    const throttlePct = Math.round((t.throttle || 0) * 100);
    const brakePct    = Math.round((t.brake    || 0) * 100);
    document.getElementById('t-throttle-bar').style.width  = throttlePct + '%';
    document.getElementById('t-throttle-val').textContent  = throttlePct + '%';
    document.getElementById('t-brake-bar').style.width     = brakePct + '%';
    document.getElementById('t-brake-val').textContent     = brakePct + '%';

    // Input trace panel (normalize clutch: F1 sends 0-100, LMU sends 0.0-1.0)
    const clutchNorm = isF1 ? (t.clutch || 0) / 100 : (t.clutch || 0);
    inputTrace.update(t.throttle || 0, t.brake || 0, clutchNorm, t.steer || 0);

    // Lap times
    if (isF1) {
        document.getElementById('t-cur-lap').textContent  = fmtMs(lap.current_lap_time);
        document.getElementById('t-last-lap').textContent = fmtMs(lap.last_lap_time);
        document.getElementById('t-best-lap').textContent = fmtMs(lap.best_lap_time);
        document.getElementById('t-s1').textContent       = fmtSectorMs(lap.sector1_time);
        document.getElementById('t-s2').textContent       = fmtSectorMs(lap.sector2_time);
    } else {
        document.getElementById('t-cur-lap').textContent  = fmtSec(lap.current_lap_time);
        document.getElementById('t-last-lap').textContent = fmtSec(lap.last_lap_time);
        document.getElementById('t-best-lap').textContent = fmtSec(lap.best_lap_time);
        document.getElementById('t-s1').textContent       = fmtSectorSec(lap.sector1_time);
        document.getElementById('t-s2').textContent       = fmtSectorSec(lap.sector2_time);
    }

    // Tyre temps — F1 has them; LMU plugin may not provide them
    const tyreSrc  = isF1 ? (t.tyres_surface_temp || [0,0,0,0]) : null;
    const tyreKeys = ['fl','fr','rl','rr'];
    tyreKeys.forEach((k, i) => {
        const box  = document.getElementById('tyre-' + k);
        const val  = document.getElementById('tyre-' + k + '-val');
        const temp = tyreSrc ? tyreSrc[i] : null;
        box.className    = 'tyre-box ' + (temp != null ? tyreColorClass(temp) : '');
        val.textContent  = temp != null ? temp : '--';
    });

    // Engine panel
    if (isF1) {
        document.getElementById('engine-f1').style.display = '';
        document.getElementById('engine-lmu').style.display = 'none';
        document.getElementById('t-engine-temp').textContent = t.engine_temp || 0;
    } else {
        document.getElementById('engine-f1').style.display = 'none';
        document.getElementById('engine-lmu').style.display = '';
        document.getElementById('t-water-temp').textContent =
            t.engine_water_temp != null ? Math.round(t.engine_water_temp) : '--';
        document.getElementById('t-oil-temp').textContent =
            t.engine_oil_temp   != null ? Math.round(t.engine_oil_temp)   : '--';
    }

    // Class ring — LMU only
    showClassRing(!isF1);
    if (!isF1) {
        const lights = document.querySelector('.class-ring-lights');
        lights.classList.toggle('disconnected', !data.connected);
        if (data.connected) updateClassRing(t.vehicle_class || '');
    }
}

// ---------- SSE connection ----------
function connect(game) {
    if (es) { es.close(); es = null; }

    document.getElementById('conn-badge').textContent  = 'Connecting...';
    document.getElementById('conn-badge').className    = 'badge bg-secondary';

    es = new EventSource(`/api/telemetry/stream?game=${game}`);

    es.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            render(data);
            if (data.connected) hideNoSignal();
            else showNoSignal();
        } catch (_) {}
    };

    es.onerror = () => {
        document.getElementById('conn-badge').textContent = 'Disconnected';
        document.getElementById('conn-badge').className   = 'badge bg-danger';
        showNoSignal();
    };
}

// ---------- recording ----------
function setRecordingUI(recording, path) {
    isRecording = recording;
    const btn   = document.getElementById('record-btn');
    const label = document.getElementById('record-label');
    const badge = document.getElementById('record-badge');

    if (recording) {
        btn.classList.replace('btn-outline-danger', 'btn-danger');
        label.textContent = 'Stop';
        badge.style.display = '';
        badge.className = 'badge bg-danger';
        badge.textContent = path ? path.split('/').pop() : 'Recording...';
    } else {
        btn.classList.replace('btn-danger', 'btn-outline-danger');
        label.textContent = 'Record';
        badge.style.display = 'none';
    }
}

async function startRecording(game) {
    const res  = await fetch('/api/record/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({game})
    });
    const data = await res.json();
    setRecordingUI(true, data.path);
}

async function stopRecording() {
    await fetch('/api/record/stop', {method: 'POST'});
    setRecordingUI(false, null);
}

document.getElementById('record-btn').addEventListener('click', async () => {
    if (isRecording) {
        await stopRecording();
    } else {
        await startRecording(gameFamily(activeGame));
    }
});

// ---------- game select dropdown ----------
document.querySelectorAll('#game-select .dropdown-item').forEach(item => {
    item.addEventListener('click', async (e) => {
        e.preventDefault();
        document.querySelectorAll('#game-select .dropdown-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');

        activeGame = item.dataset.game;
        document.getElementById('game-select-btn').textContent = item.textContent.trim();

        // Swap DRS/Fuel label
        document.getElementById('label-drs-fuel').textContent =
            gameFamily(activeGame) === 'f1' ? 'DRS' : 'Fuel';

        // If recording, stop the old game and start one for the new game
        if (isRecording) {
            await stopRecording();
            await startRecording(gameFamily(activeGame));
        }

        connect(gameFamily(activeGame));
    });
});

// ---------- help modal: sync tab to active game ----------
document.getElementById('connect-modal').addEventListener('show.bs.modal', () => {
    const tabId = gameFamily(activeGame) === 'lmu' ? 'tab-lmu' : 'tab-f1';
    bootstrap.Tab.getOrCreateInstance(document.getElementById(tabId)).show();
});

// ---------- boot ----------
connect('f1');
