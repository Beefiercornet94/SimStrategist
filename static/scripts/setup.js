document.addEventListener('DOMContentLoaded', function () {
    var themeToggle = document.getElementById('theme-toggle');
    var fontSlider  = document.getElementById('font-size-slider');
    var fontLabel   = document.getElementById('font-size-label');

    var savedTheme = localStorage.getItem('ss-theme')     || 'dark';
    var savedFont  = localStorage.getItem('ss-font-size') || '16';

    themeToggle.checked = savedTheme === 'light';
    fontSlider.value    = savedFont;
    fontLabel.textContent = savedFont + 'px';

    themeToggle.addEventListener('change', function () {
        var theme = this.checked ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('ss-theme', theme);
    });

    fontSlider.addEventListener('input', function () {
        var size = this.value;
        document.documentElement.style.setProperty('--base-font-size', size + 'px');
        localStorage.setItem('ss-font-size', size);
        fontLabel.textContent = size + 'px';
    });
});
