document.addEventListener('DOMContentLoaded', function () {
    var fontSlider = document.getElementById('font-size-slider');
    var fontLabel  = document.getElementById('font-size-label');

    var savedTheme = localStorage.getItem('ss-theme')     || 'dark';
    var savedFont  = localStorage.getItem('ss-font-size') || '16';

    fontSlider.value      = savedFont;
    fontLabel.textContent = savedFont + 'px';

    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('ss-theme', theme);
        document.getElementById('theme-dark').classList.toggle('theme-option-active',  theme === 'dark');
        document.getElementById('theme-light').classList.toggle('theme-option-active', theme === 'light');
    }

    setTheme(savedTheme);

    document.getElementById('theme-dark').addEventListener('click',  function () { setTheme('dark');  });
    document.getElementById('theme-light').addEventListener('click', function () { setTheme('light'); });

    fontSlider.addEventListener('input', function () {
        var size = this.value;
        document.documentElement.style.setProperty('--base-font-size', size + 'px');
        localStorage.setItem('ss-font-size', size);
        fontLabel.textContent = size + 'px';
    });

    // Simulator toggle
    document.querySelectorAll('#sim-toggle button').forEach(function (btn) {
        btn.addEventListener('click', function () {
            document.querySelectorAll('#sim-toggle button').forEach(function (b) {
                b.classList.replace('btn-primary', 'btn-outline-primary');
                b.classList.remove('active');
            });
            btn.classList.replace('btn-outline-primary', 'btn-primary');
            btn.classList.add('active');

            var sim = btn.dataset.sim;
            document.getElementById('instructions-f1').style.display  = sim === 'f1'  ? '' : 'none';
            document.getElementById('instructions-lmu').style.display = sim === 'lmu' ? '' : 'none';
        });
    });
});
