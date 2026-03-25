/* F1 Next Session Countdown */
(function () {
    let targetTime = null;

    function pad(n) {
        return String(n).padStart(2, '0');
    }

    function tick() {
        if (!targetTime) return;
        const now = Date.now();
        const diff = targetTime - now;

        if (diff <= 0) {
            // Session has started — re-fetch to get the next one
            loadNextSession();
            return;
        }

        const totalSeconds = Math.floor(diff / 1000);
        const days    = Math.floor(totalSeconds / 86400);
        const hours   = Math.floor((totalSeconds % 86400) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;

        document.getElementById('cd-days').textContent    = pad(days);
        document.getElementById('cd-hours').textContent   = pad(hours);
        document.getElementById('cd-minutes').textContent = pad(minutes);
        document.getElementById('cd-seconds').textContent = pad(seconds);
    }

    function loadNextSession() {
        fetch('/api/f1/next-session')
            .then(r => r.json())
            .then(data => {
                const el = document.getElementById('f1-countdown');
                if (!el) return;

                if (data.none) {
                    el.innerHTML = '<p class="text-secondary">No upcoming F1 sessions found.</p>';
                    return;
                }

                targetTime = new Date(data.isoTime).getTime();

                const localTime = new Date(data.isoTime).toLocaleString(undefined, {
                    weekday: 'short', month: 'short', day: 'numeric',
                    hour: '2-digit', minute: '2-digit', timeZoneName: 'short'
                });

                document.getElementById('cd-gp-name').textContent      = data.grandPrix;
                document.getElementById('cd-session-name').textContent  = data.session;
                document.getElementById('cd-circuit').textContent       = data.circuit;
                document.getElementById('cd-local-time').textContent    = localTime;
                document.getElementById('cd-round').textContent         = 'Round ' + data.round;

                el.style.display = '';
                tick();
            })
            .catch(() => {});
    }

    document.addEventListener('DOMContentLoaded', function () {
        loadNextSession();
        setInterval(tick, 1000);
    });
})();
