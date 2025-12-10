/**
 * Auto Translation System for Inify
 * Uses Google Translate API for automatic translation
 */

(function() {
    'use strict';
    
    const STORAGE_KEY = 'inify_language';
    
    // Get current language
    function getCurrentLanguage() {
        return localStorage.getItem(STORAGE_KEY) || 'ar';
    }
    
    // Set language
    function setLanguage(lang) {
        localStorage.setItem(STORAGE_KEY, lang);
    }
    
    // Toggle language
    window.toggleLanguageAndReload = function() {
        const currentLang = getCurrentLanguage();
        const newLang = currentLang === 'ar' ? 'en' : 'ar';
        setLanguage(newLang);
        
        // If switching to Arabic, reset Google Translate cookie
        if (newLang === 'ar') {
            // Clear Google Translate cookie
            document.cookie = 'googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
            document.cookie = 'googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=' + window.location.hostname;
            document.cookie = 'googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=.' + window.location.hostname;
            
            // Reset to original page
            const select = document.querySelector('.goog-te-combo');
            if (select) {
                select.value = 'ar';
                select.dispatchEvent(new Event('change'));
            }
        }
        
        location.reload();
    };
    
    // Initialize Google Translate
    function initGoogleTranslate() {
        const lang = getCurrentLanguage();
        
        // Only load Google Translate if English is selected
        if (lang === 'en') {
            // Add Google Translate script
            const script = document.createElement('script');
            script.src = '//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
            script.async = true;
            document.head.appendChild(script);
            
            // Create hidden translate element
            const translateDiv = document.createElement('div');
            translateDiv.id = 'google_translate_element';
            translateDiv.style.display = 'none';
            document.body.appendChild(translateDiv);
        }
    }
    
    // Google Translate callback
    window.googleTranslateElementInit = function() {
        new google.translate.TranslateElement({
            pageLanguage: 'ar',
            includedLanguages: 'en',
            autoDisplay: false
        }, 'google_translate_element');
        
        // Auto-translate to English
        setTimeout(() => {
            triggerTranslation('en');
        }, 500);
    };
    
    // Trigger translation
    function triggerTranslation(targetLang) {
        const select = document.querySelector('.goog-te-combo');
        if (select) {
            select.value = targetLang;
            select.dispatchEvent(new Event('change'));
            
            // Update page direction
            setTimeout(() => {
                document.documentElement.dir = 'ltr';
                document.documentElement.lang = 'en';
                updateLanguageButtons();
            }, 100);
        }
    }
    
    // Update language toggle buttons
    function updateLanguageButtons() {
        const lang = getCurrentLanguage();
        const buttons = document.querySelectorAll('#langToggleBtn, #langToggleBtnTop, [onclick*="toggleLanguage"]');
        
        buttons.forEach(btn => {
            if (lang === 'en') {
                btn.innerHTML = '🌐 عربي';
            } else {
                btn.innerHTML = '🌐 EN';
            }
        });
    }
    
    // Hide Google Translate banner
    function hideGoogleTranslateBanner() {
        const style = document.createElement('style');
        style.textContent = `
            .goog-te-banner-frame, 
            .skiptranslate,
            #goog-gt-tt,
            .goog-te-balloon-frame,
            div#goog-gt-,
            .goog-text-highlight {
                display: none !important;
            }
            body {
                top: 0 !important;
            }
            .goog-te-gadget {
                display: none !important;
            }
        `;
        document.head.appendChild(style);
    }
    
    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        hideGoogleTranslateBanner();
        updateLanguageButtons();
        
        const lang = getCurrentLanguage();
        
        if (lang === 'en') {
            // Set LTR direction and load Google Translate
            document.documentElement.dir = 'ltr';
            document.documentElement.lang = 'en';
            initGoogleTranslate();
        } else {
            // Keep Arabic - RTL direction, no translation
            document.documentElement.dir = 'rtl';
            document.documentElement.lang = 'ar';
        }
    });
    
    // Expose functions globally
    window.inifyTranslate = {
        getCurrentLanguage,
        setLanguage,
        toggleLanguage: window.toggleLanguageAndReload
    };
})();
