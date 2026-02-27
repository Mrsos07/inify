// ═══════════════════════════════════════════════════════════
// Theme Toggle (Dark/Light Mode) - Global Script
// ═══════════════════════════════════════════════════════════

// Light mode CSS variable overrides
var _lightVars = {
    '--midnight': '#FAFBFC',
    '--dark-blue': '#F0F2F5',
    '--pearl': '#1F2937',
    '--text-muted': 'rgba(31,41,55,0.7)',
    '--card-bg': '#FFFFFF',
    '--border': 'rgba(0,0,0,0.1)'
};

// Dark mode CSS variable defaults
var _darkVars = {
    '--midnight': '#0A1628',
    '--dark-blue': '#1E3A5F',
    '--pearl': '#F8F8F8',
    '--text-muted': 'rgba(248,248,248,0.6)',
    '--card-bg': 'rgba(30,58,95,0.4)',
    '--border': 'rgba(107,184,201,0.15)'
};

function getTheme() {
    return localStorage.getItem('inify_theme') || 'dark';
}

function setTheme(theme) {
    localStorage.setItem('inify_theme', theme);
    var root = document.documentElement;

    if (theme === 'light') {
        root.classList.add('light-mode');
        if (document.body) document.body.classList.add('light-mode');
        // Force override CSS variables on :root to beat inline <style> specificity
        for (var k in _lightVars) root.style.setProperty(k, _lightVars[k], 'important');
    } else {
        root.classList.remove('light-mode');
        if (document.body) document.body.classList.remove('light-mode');
        // Restore dark defaults and remove inline overrides
        for (var k in _darkVars) root.style.removeProperty(k);
    }

    // Force repaint on elements with hardcoded dark gradients
    _fixHardcodedBackgrounds(theme);

    updateThemeButton();
}

function _fixHardcodedBackgrounds(theme) {
    // Fix .premium-bg and body background that use hardcoded gradients
    var premiumBg = document.querySelector('.premium-bg');
    var gridPattern = document.querySelector('.grid-pattern');

    if (theme === 'light') {
        if (document.body) document.body.style.background = '#FAFBFC';
        if (premiumBg) premiumBg.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:-1;background:#FAFBFC !important;';
        if (gridPattern) gridPattern.style.display = 'none';
    } else {
        if (document.body) document.body.style.background = '';
        if (premiumBg) premiumBg.style.cssText = '';
        if (gridPattern) gridPattern.style.display = '';
    }
}

function toggleTheme() {
    var currentTheme = getTheme();
    var newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
}

function updateThemeButton() {
    var theme = getTheme();
    var btn = document.getElementById('themeToggleBtn');
    var mobileThemeLinks = document.querySelectorAll('.mobile-menu-links a[onclick*="toggleTheme"]');

    var sunSVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
    var moonSVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

    if (btn) {
        var isSidebarBtn = btn.closest('.sidebar-footer') || btn.closest('.sidebar');
        if (isSidebarBtn) {
            btn.innerHTML = (theme === 'dark' ? sunSVG + ' الوضع الفاتح' : moonSVG + ' الوضع الداكن');
        } else {
            btn.innerHTML = theme === 'dark' ? sunSVG : moonSVG;
        }
        btn.title = theme === 'dark' ? 'التبديل للوضع الفاتح' : 'التبديل للوضع الداكن';
    }

    mobileThemeLinks.forEach(function(link) {
        link.innerHTML = theme === 'dark' ? sunSVG + ' الوضع الفاتح' : moonSVG + ' الوضع الداكن';
    });
}

// Initialize theme on page load - run immediately
// Apply to <html> first (always available), then <body> when ready
(function initTheme() {
    var theme = getTheme();
    var root = document.documentElement;

    if (theme === 'light') {
        root.classList.add('light-mode');
        for (var k in _lightVars) root.style.setProperty(k, _lightVars[k], 'important');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            if (theme === 'light') {
                document.body.classList.add('light-mode');
                _fixHardcodedBackgrounds('light');
            }
            updateThemeButton();
        });
    } else {
        if (theme === 'light' && document.body) {
            document.body.classList.add('light-mode');
            _fixHardcodedBackgrounds('light');
        }
        updateThemeButton();
    }
})();
