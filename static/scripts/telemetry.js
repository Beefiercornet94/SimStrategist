// ---------- constants ----------
const F1_SESSION_TYPES = {
    0:'Unknown', 1:'Practice 1', 2:'Practice 2', 3:'Practice 3',
    4:'Short Practice', 5:'Qualifying 1', 6:'Qualifying 2', 7:'Qualifying 3',
    8:'Short Qualifying', 9:'One-Shot Qualifying', 10:'Race', 11:'Race 2',
    12:'Race 3', 13:'Time Trial'
};

// ---------- state ----------
let activeGame = 'f1';
let es = null;   // active EventSource

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
    const isF1    = activeGame === 'f1';

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
}

// ---------- SSE connection ----------
function connect(game) {
    if (es) { es.close(); es = null; }

    document.getElementById('conn-badge').textContent  = 'Connecting...';
    document.getElementById('conn-badge').className    = 'badge bg-secondary';

    es = new EventSource(`/api/telemetry/stream?game=${game}`);

    es.onmessage = (e) => {
        try { render(JSON.parse(e.data)); } catch (_) {}
    };

    es.onerror = () => {
        document.getElementById('conn-badge').textContent = 'Disconnected';
        document.getElementById('conn-badge').className   = 'badge bg-danger';
    };
}

// ---------- toggle ----------
document.querySelectorAll('#game-toggle button').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('#game-toggle button').forEach(b => {
            b.classList.replace('btn-primary', 'btn-outline-primary');
            b.classList.remove('active');
        });
        btn.classList.replace('btn-outline-primary', 'btn-primary');
        btn.classList.add('active');

        activeGame = btn.dataset.game;

        // Swap DRS/Fuel label
        document.getElementById('label-drs-fuel').textContent =
            activeGame === 'f1' ? 'DRS' : 'Fuel';

        connect(activeGame);
    });
});

// ---------- help modal: sync tab to active game ----------
document.getElementById('connect-modal').addEventListener('show.bs.modal', () => {
    const tabId = activeGame === 'lmu' ? 'tab-lmu' : 'tab-f1';
    bootstrap.Tab.getOrCreateInstance(document.getElementById(tabId)).show();
});

// ---------- boot ----------
connect('f1');
