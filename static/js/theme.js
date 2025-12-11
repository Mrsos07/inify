// ═══════════════════════════════════════════════════════════
// Theme Toggle (Dark/Light Mode) - Global Script
// ═══════════════════════════════════════════════════════════

function getTheme() {
    return localStorage.getItem('inify_theme') || 'dark';
}

function setTheme(theme) {
    localStorage.setItem('inify_theme', theme);
    if (theme === 'light') {
        document.body.classList.add('light-mode');
    } else {
        document.body.classList.remove('light-mode');
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
        // Check if it's a sidebar button (has full text) or header button (icon only)
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
(function initTheme() {
    const theme = getTheme();
    // Apply theme class immediately to prevent flash
    if (theme === 'light') {
        document.body.classList.add('light-mode');
    }
    // Update button after DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', updateThemeButton);
    } else {
        updateThemeButton();
    }
})();
