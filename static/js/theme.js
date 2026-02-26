// ═══════════════════════════════════════════════════════════
// Theme Toggle (Dark/Light Mode) - Global Script
// ═══════════════════════════════════════════════════════════

function getTheme() {
    return localStorage.getItem('inify_theme') || 'dark';
}

function setTheme(theme) {
    localStorage.setItem('inify_theme', theme);
    if (theme === 'light') {
        document.documentElement.classList.add('light-mode');
        if (document.body) document.body.classList.add('light-mode');
    } else {
        document.documentElement.classList.remove('light-mode');
        if (document.body) document.body.classList.remove('light-mode');
    }
    updateThemeButton();
}

function toggleTheme() {
    const currentTheme = getTheme();
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
}

function updateThemeButton() {
    const theme = getTheme();
    const btn = document.getElementById('themeToggleBtn');
    const mobileThemeLinks = document.querySelectorAll('.mobile-menu-links a[onclick*="toggleTheme"]');
    
    if (btn) {
        const isSidebarBtn = btn.closest('.sidebar-footer') || btn.closest('.sidebar');
        if (isSidebarBtn) {
            btn.innerHTML = theme === 'dark' ? '☀️ الوضع الفاتح' : '🌙 الوضع الداكن';
        } else {
            btn.innerHTML = theme === 'dark' ? '☀️' : '🌙';
        }
        btn.title = theme === 'dark' ? 'التبديل للوضع الفاتح' : 'التبديل للوضع الداكن';
    }
    
    mobileThemeLinks.forEach(link => {
        if (theme === 'dark') {
            link.innerHTML = '☀️ الوضع الفاتح';
        } else {
            link.innerHTML = '🌙 الوضع الداكن';
        }
    });
}

// Initialize theme on page load - run immediately
// Apply to <html> first (always available), then <body> when ready
(function initTheme() {
    const theme = getTheme();
    if (theme === 'light') {
        document.documentElement.classList.add('light-mode');
    }
    // Also apply to body once DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            if (theme === 'light') document.body.classList.add('light-mode');
            updateThemeButton();
        });
    } else {
        if (theme === 'light' && document.body) document.body.classList.add('light-mode');
        updateThemeButton();
    }
})();
