// ---------- Input Trace Module ----------
// Manages the driver inputs panel: bars and graph mode.
// Exposes: inputTrace.update(throttle, brake, clutch, steer)

const inputTrace = (() => {
    // ---- Constants ----
    const GRAPH_POINTS = 300;   // Number of frames to keep in history
    const COLORS = {
        throttle: '#00ff87',
        brake:    '#ff4757',
        clutch:   '#4d9fec',
        steer:    '#999999',
    };

    // ---- State ----
    let mode = 'bars';

    // Rolling buffers for graph mode (values 0..1 for all channels)
    const history = {
        throttle: new Float32Array(GRAPH_POINTS),
        brake:    new Float32Array(GRAPH_POINTS),
        clutch:   new Float32Array(GRAPH_POINTS),
        steer:    new Float32Array(GRAPH_POINTS),  // stored as 0..1 (0.5 = center)
    };
    let historyHead = 0;
    let historyCount = 0;

    // ---- DOM refs ----
    const barsEl     = document.getElementById('input-bars');
    const graphEl    = document.getElementById('input-graph');
    const canvas     = document.getElementById('input-canvas');
    const ctx        = canvas.getContext('2d');

    // Bars
    const throttleBar = document.getElementById('it-throttle-bar');
    const brakeBar    = document.getElementById('it-brake-bar');
    const clutchBar   = document.getElementById('it-clutch-bar');
    const steerBar    = document.getElementById('it-steer-bar');

    const throttleVal = document.getElementById('it-throttle-val');
    const brakeVal    = document.getElementById('it-brake-val');
    const clutchVal   = document.getElementById('it-clutch-val');
    const steerVal    = document.getElementById('it-steer-val');

    // ---- Canvas resize ----
    function resizeCanvas() {
        const rect = canvas.parentElement.getBoundingClientRect();
        if (rect.width > 0) {
            canvas.width  = Math.round(rect.width * window.devicePixelRatio);
            canvas.height = Math.round(120    * window.devicePixelRatio);
            canvas.style.width  = rect.width + 'px';
            canvas.style.height = '120px';
        }
    }

    // ---- Mode toggle ----
    document.getElementById('input-mode-toggle').addEventListener('click', (e) => {
        const btn = e.target.closest('[data-mode]');
        if (!btn) return;
        mode = btn.dataset.mode;

        document.querySelectorAll('#input-mode-toggle [data-mode]').forEach(b => {
            b.classList.toggle('btn-primary',         b === btn);
            b.classList.toggle('btn-outline-primary', b !== btn);
            b.classList.toggle('active',              b === btn);
        });

        barsEl.style.display  = mode === 'bars'  ? '' : 'none';
        graphEl.style.display = mode === 'graph' ? '' : 'none';

        if (mode === 'graph') {
            resizeCanvas();
        }
    });

    window.addEventListener('resize', () => {
        if (mode === 'graph') resizeCanvas();
    });

    // ---- Update bars ----
    function updateBars(throttle, brake, clutch, steer) {
        const tPct = Math.round(throttle * 100);
        const bPct = Math.round(brake    * 100);
        const cPct = Math.round(clutch   * 100);  // 0.0-1.0 → 0-100
        const sPct = Math.round(steer    * 100);  // -100 to 100

        throttleBar.style.width = tPct + '%';
        brakeBar.style.width    = bPct + '%';
        clutchBar.style.width   = cPct + '%';

        throttleVal.textContent = tPct + '%';
        brakeVal.textContent    = bPct + '%';
        clutchVal.textContent   = cPct + '%';

        // Steering: center-origin bar
        if (sPct >= 0) {
            // Right turn: bar starts at center, goes right
            steerBar.style.left  = '50%';
            steerBar.style.width = (sPct / 2) + '%';
        } else {
            // Left turn: bar ends at center, starts left
            const w = (-sPct / 2);
            steerBar.style.left  = (50 - w) + '%';
            steerBar.style.width = w + '%';
        }

        const sLabel = sPct > 0 ? 'R' + Math.abs(sPct) + '%'
                     : sPct < 0 ? 'L' + Math.abs(sPct) + '%'
                     : '0%';
        steerVal.textContent = sLabel;
    }

    // ---- Update graph history ----
    function pushHistory(throttle, brake, clutch, steer) {
        history.throttle[historyHead] = Math.min(1, Math.max(0, throttle));
        history.brake[historyHead]    = Math.min(1, Math.max(0, brake));
        history.clutch[historyHead]   = Math.min(1, Math.max(0, clutch));
        history.steer[historyHead]    = (steer + 1) / 2;  // -1..1 → 0..1 (0.5 = center)

        historyHead  = (historyHead + 1) % GRAPH_POINTS;
        historyCount = Math.min(historyCount + 1, GRAPH_POINTS);
    }

    // ---- Draw graph ----
    function drawGraph() {
        if (historyCount === 0) return;

        const w   = canvas.width;
        const h   = canvas.height;
        const dpr = window.devicePixelRatio || 1;

        ctx.clearRect(0, 0, w, h);

        // Dark background
        ctx.fillStyle = 'rgba(0,0,0,0.35)';
        ctx.fillRect(0, 0, w, h);

        // Steering center line
        const centerY = h / 2;
        ctx.strokeStyle = 'rgba(255,255,255,0.12)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4 * dpr, 4 * dpr]);
        ctx.beginPath();
        ctx.moveTo(0, centerY);
        ctx.lineTo(w, centerY);
        ctx.stroke();
        ctx.setLineDash([]);

        const count = historyCount;
        const channels = [
            { buf: history.throttle, color: COLORS.throttle, flip: true  },
            { buf: history.brake,    color: COLORS.brake,    flip: true  },
            { buf: history.clutch,   color: COLORS.clutch,   flip: true  },
            { buf: history.steer,    color: COLORS.steer,    flip: false },
        ];

        for (const ch of channels) {
            ctx.strokeStyle = ch.color;
            ctx.lineWidth   = 1.5 * dpr;
            ctx.beginPath();

            for (let i = 0; i < count; i++) {
                // Index in circular buffer: oldest first
                const bufIdx = (historyHead - count + i + GRAPH_POINTS) % GRAPH_POINTS;
                const val    = ch.buf[bufIdx];
                const x      = (i / (count - 1 || 1)) * w;
                // flip=true means 0 at bottom, 1 at top (standard for throttle/brake)
                // flip=false means 0.5 at center (steering)
                const y = ch.flip
                    ? (1 - val) * (h - 4 * dpr) + 2 * dpr
                    : (1 - val) * (h - 4 * dpr) + 2 * dpr;

                if (i === 0) ctx.moveTo(x, y);
                else         ctx.lineTo(x, y);
            }
            ctx.stroke();
        }
    }

    // ---- Public API ----
    function update(throttle, brake, clutch, steer) {
        pushHistory(throttle, brake, clutch, steer);

        if (mode === 'bars') {
            updateBars(throttle, brake, clutch, steer);
        } else {
            drawGraph();
        }
    }

    return { update };
})();
