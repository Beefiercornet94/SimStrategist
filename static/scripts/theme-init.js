// Applied immediately in <head> to prevent flash of wrong theme/size
(function () {
    var theme    = localStorage.getItem('ss-theme')     || 'dark';
    var fontSize = localStorage.getItem('ss-font-size') || '16';
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.style.setProperty('--base-font-size', fontSize + 'px');
}());
