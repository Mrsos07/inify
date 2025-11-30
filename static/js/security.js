/**
 * Inify Security Module
 * =====================
 * OWASP Top 10 Protection
 * 
 * 🔒 يحمي من:
 * - A03:2021 – Injection (XSS)
 * - A07:2021 – Cross-Site Scripting
 * - A08:2021 – Software and Data Integrity Failures
 */

const InifySecurity = {
    
    // ═══════════════════════════════════════════════════════════════
    // 🛡️ A03 & A07: XSS Protection - تنظيف المدخلات
    // ═══════════════════════════════════════════════════════════════
    
    /**
     * تنظيف النص من أكواد HTML الضارة
     * @param {string} text - النص المراد تنظيفه
     * @returns {string} - النص النظيف
     */
    escapeHtml(text) {
        if (typeof text !== 'string') return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;',
            '/': '&#x2F;',
            '`': '&#x60;',
            '=': '&#x3D;'
        };
        return text.replace(/[&<>"'`=\/]/g, char => map[char]);
    },

    /**
     * تنظيف النص للاستخدام في attributes
     * @param {string} text 
     * @returns {string}
     */
    escapeAttribute(text) {
        if (typeof text !== 'string') return '';
        return text.replace(/['"<>&]/g, char => {
            switch(char) {
                case '"': return '&quot;';
                case "'": return '&#39;';
                case '<': return '&lt;';
                case '>': return '&gt;';
                case '&': return '&amp;';
                default: return char;
            }
        });
    },

    /**
     * تنظيف URL من الأكواد الضارة
     * @param {string} url 
     * @returns {string}
     */
    sanitizeUrl(url) {
        if (typeof url !== 'string') return '';
        // منع javascript: و data: URLs
        const dangerous = /^(javascript|data|vbscript):/i;
        if (dangerous.test(url.trim())) {
            return '';
        }
        return this.escapeHtml(url);
    },

    /**
     * إنشاء HTML آمن من template
     * @param {string} template 
     * @param {object} data 
     * @returns {string}
     */
    safeTemplate(template, data) {
        return template.replace(/\{\{(\w+)\}\}/g, (match, key) => {
            return this.escapeHtml(data[key] || '');
        });
    },

    // ═══════════════════════════════════════════════════════════════
    // 🔐 A02: Cryptographic Failures - التشفير
    // ═══════════════════════════════════════════════════════════════

    /**
     * تشفير SHA-256 (async)
     * @param {string} text 
     * @returns {Promise<string>}
     */
    async sha256(text) {
        const encoder = new TextEncoder();
        const data = encoder.encode(text);
        const hashBuffer = await crypto.subtle.digest('SHA-256', data);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    },

    /**
     * تشفير سريع (sync)
     * @param {string} text 
     * @returns {string}
     */
    quickHash(text) {
        let hash = 0;
        for (let i = 0; i < text.length; i++) {
            const char = text.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return Math.abs(hash).toString(16);
    },

    // ═══════════════════════════════════════════════════════════════
    // 🛡️ A01: Broken Access Control - التحقق من الصلاحيات
    // ═══════════════════════════════════════════════════════════════

    /**
     * التحقق من صلاحية الوصول
     * @param {string} requiredRole 
     * @returns {boolean}
     */
    checkAccess(requiredRole) {
        const session = JSON.parse(localStorage.getItem('newra_session') || '{}');
        if (!session.loggedIn) return false;
        
        const roleHierarchy = ['free', 'marketer', 'agency', 'admin'];
        const userLevel = roleHierarchy.indexOf(session.role || 'free');
        const requiredLevel = roleHierarchy.indexOf(requiredRole);
        
        return userLevel >= requiredLevel;
    },

    // ═══════════════════════════════════════════════════════════════
    // 🔒 A04: Insecure Design - التحقق من المدخلات
    // ═══════════════════════════════════════════════════════════════

    /**
     * التحقق من صحة البريد الإلكتروني
     * @param {string} email 
     * @returns {boolean}
     */
    isValidEmail(email) {
        const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return regex.test(email);
    },

    /**
     * التحقق من صحة رقم الهاتف السعودي
     * @param {string} phone 
     * @returns {boolean}
     */
    isValidSaudiPhone(phone) {
        const cleaned = phone.replace(/\D/g, '');
        // 05xxxxxxxx or 966xxxxxxxx
        return /^(05\d{8}|966\d{9})$/.test(cleaned);
    },

    /**
     * التحقق من قوة كلمة المرور
     * @param {string} password 
     * @returns {object}
     */
    checkPasswordStrength(password) {
        const result = {
            isStrong: false,
            score: 0,
            feedback: []
        };

        if (password.length >= 8) result.score++;
        else result.feedback.push('يجب أن تكون 8 أحرف على الأقل');

        if (/[a-z]/.test(password)) result.score++;
        else result.feedback.push('أضف حروف صغيرة');

        if (/[A-Z]/.test(password)) result.score++;
        else result.feedback.push('أضف حروف كبيرة');

        if (/[0-9]/.test(password)) result.score++;
        else result.feedback.push('أضف أرقام');

        if (/[^a-zA-Z0-9]/.test(password)) result.score++;
        else result.feedback.push('أضف رموز خاصة');

        result.isStrong = result.score >= 4;
        return result;
    },

    // ═══════════════════════════════════════════════════════════════
    // 🛡️ A05: Security Misconfiguration - الإعدادات الآمنة
    // ═══════════════════════════════════════════════════════════════

    /**
     * إضافة CSP headers (للاستخدام مع backend)
     * @returns {object}
     */
    getSecurityHeaders() {
        return {
            'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' https://accounts.google.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://generativelanguage.googleapis.com",
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'SAMEORIGIN',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        };
    },

    // ═══════════════════════════════════════════════════════════════
    // 🔐 A09: Security Logging - التسجيل الأمني
    // ═══════════════════════════════════════════════════════════════

    /**
     * تسجيل حدث أمني
     * @param {string} event 
     * @param {object} details 
     */
    logSecurityEvent(event, details = {}) {
        const log = {
            timestamp: new Date().toISOString(),
            event: event,
            details: details,
            userAgent: navigator.userAgent,
            url: window.location.href
        };
        
        // حفظ في localStorage (في الإنتاج، أرسل للسيرفر)
        const logs = JSON.parse(localStorage.getItem('security_logs') || '[]');
        logs.push(log);
        // احتفظ بآخر 100 سجل فقط
        if (logs.length > 100) logs.shift();
        localStorage.setItem('security_logs', JSON.stringify(logs));
        
        // تحذير في Console للتطوير
        console.warn('🔒 Security Event:', event, details);
    },

    // ═══════════════════════════════════════════════════════════════
    // 🛡️ Rate Limiting - الحد من المحاولات
    // ═══════════════════════════════════════════════════════════════

    rateLimits: {},

    /**
     * التحقق من الحد الأقصى للمحاولات
     * @param {string} action 
     * @param {number} maxAttempts 
     * @param {number} windowMs 
     * @returns {boolean}
     */
    checkRateLimit(action, maxAttempts = 5, windowMs = 60000) {
        const now = Date.now();
        const key = action;
        
        if (!this.rateLimits[key]) {
            this.rateLimits[key] = { attempts: 0, resetTime: now + windowMs };
        }
        
        if (now > this.rateLimits[key].resetTime) {
            this.rateLimits[key] = { attempts: 0, resetTime: now + windowMs };
        }
        
        this.rateLimits[key].attempts++;
        
        if (this.rateLimits[key].attempts > maxAttempts) {
            this.logSecurityEvent('RATE_LIMIT_EXCEEDED', { action, attempts: this.rateLimits[key].attempts });
            return false;
        }
        
        return true;
    },

    // ═══════════════════════════════════════════════════════════════
    // 🔒 CSRF Protection
    // ═══════════════════════════════════════════════════════════════

    /**
     * إنشاء CSRF token
     * @returns {string}
     */
    generateCSRFToken() {
        const array = new Uint8Array(32);
        crypto.getRandomValues(array);
        const token = Array.from(array, b => b.toString(16).padStart(2, '0')).join('');
        sessionStorage.setItem('csrf_token', token);
        return token;
    },

    /**
     * التحقق من CSRF token
     * @param {string} token 
     * @returns {boolean}
     */
    validateCSRFToken(token) {
        const storedToken = sessionStorage.getItem('csrf_token');
        return storedToken && storedToken === token;
    },

    // ═══════════════════════════════════════════════════════════════
    // 🛡️ Session Security
    // ═══════════════════════════════════════════════════════════════

    /**
     * التحقق من صلاحية الجلسة
     * @param {number} maxAgeHours 
     * @returns {boolean}
     */
    isSessionValid(maxAgeHours = 24) {
        const session = JSON.parse(localStorage.getItem('newra_session') || '{}');
        if (!session.loggedIn || !session.loginTime) return false;
        
        const loginTime = new Date(session.loginTime).getTime();
        const now = Date.now();
        const maxAge = maxAgeHours * 60 * 60 * 1000;
        
        if (now - loginTime > maxAge) {
            this.logSecurityEvent('SESSION_EXPIRED', { loginTime: session.loginTime });
            localStorage.removeItem('newra_session');
            return false;
        }
        
        return true;
    },

    /**
     * تجديد الجلسة
     */
    refreshSession() {
        const session = JSON.parse(localStorage.getItem('newra_session') || '{}');
        if (session.loggedIn) {
            session.lastActivity = new Date().toISOString();
            localStorage.setItem('newra_session', JSON.stringify(session));
        }
    }
};

// تصدير للاستخدام العام
window.InifySecurity = InifySecurity;

// تهيئة CSRF token عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', () => {
    InifySecurity.generateCSRFToken();
    InifySecurity.refreshSession();
});

// تحديث الجلسة عند النشاط
document.addEventListener('click', () => InifySecurity.refreshSession());
document.addEventListener('keypress', () => InifySecurity.refreshSession());
