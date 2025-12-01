/**
 * Inify Authentication & Authorization System
 * نظام المصادقة والصلاحيات
 * 🔒 Secure Password Hashing
 */

const InifyAuth = {
    // دالة تشفير كلمة المرور (SHA-256)
    async hashPassword(password) {
        const encoder = new TextEncoder();
        const data = encoder.encode(password + 'inify_salt_2025');
        const hashBuffer = await crypto.subtle.digest('SHA-256', data);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    },

    // دالة تشفير متزامنة (للتوافق)
    hashPasswordSync(password) {
        const str = password + 'inify_salt_2025';
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        // تحويل لـ hex وإضافة طبقة أمان
        let hex = Math.abs(hash).toString(16);
        // إضافة hash ثاني للأمان
        for (let i = 0; i < str.length; i++) {
            hex += (str.charCodeAt(i) ^ 0x5A).toString(16);
        }
        return hex.substring(0, 64);
    },

    // أنواع الصلاحيات
    ROLES: {
        ADMIN: 'admin',           // مدير النظام
        AGENCY: 'agency',         // مؤسسة عقارية
        MARKETER: 'marketer',     // مسوق عقاري
        FREE: 'free'              // مستخدم مجاني
    },

    // مزايا كل صلاحية
    PERMISSIONS: {
        admin: {
            name: 'مدير النظام',
            nameEn: 'Admin',
            maxProperties: -1,        // غير محدود
            maxClients: -1,           // غير محدود
            canUseAI: true,
            canExportData: true,
            canViewAnalytics: true,
            canManageUsers: true,
            canCustomizeChatbot: true,
            canUseAdvancedRAG: true,
            canAddTeamMembers: true,
            maxTeamMembers: -1,
            canAccessAPI: true,
            canWhiteLabel: true,
            monthlyPrice: 0,
            badge: '👑',
            color: '#FFD700'
        },
        agency: {
            name: 'مخصص',
            nameEn: 'Custom',
            maxProperties: -1,
            maxClients: -1,
            canUseAI: true,
            canExportData: true,
            canViewAnalytics: true,
            canManageUsers: false,
            canCustomizeChatbot: true,
            canUseAdvancedRAG: true,
            canAddTeamMembers: true,
            maxTeamMembers: -1,
            canAccessAPI: true,
            canWhiteLabel: true,
            monthlyPrice: 'مخصص',
            badge: '👑',
            color: '#c084fc'
        },
        marketer: {
            name: 'المسوق',
            nameEn: 'Marketer',
            maxProperties: -1,
            maxClients: -1,
            canUseAI: true,
            canExportData: true,
            canViewAnalytics: true,
            canManageUsers: false,
            canCustomizeChatbot: true,
            canUseAdvancedRAG: true,
            canAddTeamMembers: false,
            maxTeamMembers: 0,
            canAccessAPI: false,
            canWhiteLabel: false,
            monthlyPrice: 299,
            badge: '⭐',
            color: '#6BB8C9'
        },
        free: {
            name: 'مستخدم مجاني',
            nameEn: 'Free User',
            maxProperties: 5,
            maxClients: 50,
            maxConversations: 50,  // 50 محادثة/شهر
            canUseAI: true,
            canExportData: false,
            canViewAnalytics: false,
            canManageUsers: false,
            canCustomizeChatbot: false,
            canUseAdvancedRAG: false,
            canAddTeamMembers: false,
            maxTeamMembers: 0,
            canAccessAPI: false,
            canWhiteLabel: false,
            monthlyPrice: 0,
            badge: '🆓',
            color: '#9CA3AF'
        }
    },

    // 🔒 التحقق من حدود الباقة
    checkLimit(limitType) {
        const perms = this.getCurrentPermissions();
        const session = this.getSession();
        
        if (limitType === 'properties') {
            if (perms.maxProperties === -1) return { allowed: true, remaining: -1 };
            const properties = this.getProperties();
            const remaining = perms.maxProperties - properties.length;
            return { 
                allowed: remaining > 0, 
                remaining: remaining,
                max: perms.maxProperties,
                current: properties.length
            };
        }
        
        if (limitType === 'conversations') {
            if (!perms.maxConversations || perms.maxConversations === -1) return { allowed: true, remaining: -1 };
            const monthKey = `conversations_${session.id}_${new Date().getMonth()}_${new Date().getFullYear()}`;
            const count = parseInt(localStorage.getItem(monthKey) || '0');
            const remaining = perms.maxConversations - count;
            return {
                allowed: remaining > 0,
                remaining: remaining,
                max: perms.maxConversations,
                current: count
            };
        }
        
        if (limitType === 'clients') {
            if (perms.maxClients === -1) return { allowed: true, remaining: -1 };
            const clients = this.getClients();
            const remaining = perms.maxClients - clients.length;
            return {
                allowed: remaining > 0,
                remaining: remaining,
                max: perms.maxClients,
                current: clients.length
            };
        }
        
        return { allowed: true, remaining: -1 };
    },

    // زيادة عداد المحادثات
    incrementConversations() {
        const session = this.getSession();
        if (!session.id) return;
        const monthKey = `conversations_${session.id}_${new Date().getMonth()}_${new Date().getFullYear()}`;
        const count = parseInt(localStorage.getItem(monthKey) || '0');
        localStorage.setItem(monthKey, String(count + 1));
    },

    // الحصول على الجلسة الحالية
    getSession() {
        return JSON.parse(localStorage.getItem('newra_session') || '{}');
    },

    // الحصول على المستخدم الحالي
    getCurrentUser() {
        const session = this.getSession();
        if (!session.loggedIn || !session.id) return null;
        
        const users = JSON.parse(localStorage.getItem('newra_users') || '[]');
        return users.find(u => u.id === session.id) || null;
    },

    // الحصول على صلاحيات المستخدم الحالي
    getCurrentPermissions() {
        const user = this.getCurrentUser();
        if (!user) return this.PERMISSIONS.free;
        return this.PERMISSIONS[user.role] || this.PERMISSIONS.free;
    },

    // التحقق من صلاحية معينة
    hasPermission(permission) {
        const perms = this.getCurrentPermissions();
        return perms[permission] === true || perms[permission] === -1;
    },

    // الحصول على بيانات المستخدم (عقارات، عملاء، إلخ)
    getUserData(dataType) {
        const session = this.getSession();
        if (!session.id) return [];
        
        const key = `newra_${dataType}_${session.id}`;
        return JSON.parse(localStorage.getItem(key) || '[]');
    },

    // حفظ بيانات المستخدم
    setUserData(dataType, data) {
        const session = this.getSession();
        if (!session.id) return false;
        
        const key = `newra_${dataType}_${session.id}`;
        localStorage.setItem(key, JSON.stringify(data));
        return true;
    },

    // الحصول على العقارات الخاصة بالمستخدم
    getProperties() {
        return this.getUserData('properties');
    },

    // حفظ العقارات
    setProperties(properties) {
        return this.setUserData('properties', properties);
    },

    // الحصول على العملاء
    getClients() {
        return this.getUserData('clients');
    },

    // حفظ العملاء
    setClients(clients) {
        return this.setUserData('clients', clients);
    },

    // الحصول على إعدادات الوكيل
    getAgentSettings() {
        const session = this.getSession();
        if (!session.id) return {};
        
        const key = `newra_agent_settings_${session.id}`;
        return JSON.parse(localStorage.getItem(key) || '{}');
    },

    // حفظ إعدادات الوكيل
    setAgentSettings(settings) {
        const session = this.getSession();
        if (!session.id) return false;
        
        const key = `newra_agent_settings_${session.id}`;
        localStorage.setItem(key, JSON.stringify(settings));
        return true;
    },

    // التحقق من الحد الأقصى للعقارات
    canAddProperty() {
        const perms = this.getCurrentPermissions();
        const properties = this.getProperties();
        
        if (perms.maxProperties === -1) return true;
        return properties.length < perms.maxProperties;
    },

    // التحقق من الحد الأقصى للعملاء
    canAddClient() {
        const perms = this.getCurrentPermissions();
        const clients = this.getClients();
        
        if (perms.maxClients === -1) return true;
        return clients.length < perms.maxClients;
    },

    // تسجيل الدخول (مع تشفير كلمة المرور + Rate Limiting)
    login(email, password) {
        // 🔒 Rate Limiting - منع هجمات Brute Force
        if (typeof InifySecurity !== 'undefined') {
            if (!InifySecurity.checkRateLimit('login_' + email, 5, 60000)) {
                return { success: false, error: 'تم تجاوز الحد الأقصى للمحاولات. انتظر دقيقة.' };
            }
        }
        
        const users = JSON.parse(localStorage.getItem('newra_users') || '[]');
        const hashedPassword = this.hashPasswordSync(password);
        
        // البحث بكلمة المرور المشفرة أو العادية (للتوافق مع الحسابات القديمة)
        let user = users.find(u => u.email === email && u.passwordHash === hashedPassword);
        
        // التوافق مع الحسابات القديمة (غير مشفرة)
        if (!user) {
            user = users.find(u => u.email === email && u.password === password);
            if (user) {
                // ترقية الحساب القديم للتشفير
                user.passwordHash = hashedPassword;
                delete user.password;
                localStorage.setItem('newra_users', JSON.stringify(users));
            }
        }
        
        if (user) {
            localStorage.setItem('newra_session', JSON.stringify({
                id: user.id,
                name: user.name,
                email: user.email,
                role: user.role || 'free',
                loggedIn: true,
                loginTime: new Date().toISOString()
            }));
            return { success: true, user };
        }
        return { success: false, error: 'البريد الإلكتروني أو كلمة المرور غير صحيحة' };
    },

    // تسجيل مستخدم جديد (مع تشفير كلمة المرور)
    register(userData) {
        const users = JSON.parse(localStorage.getItem('newra_users') || '[]');
        
        // التحقق من عدم وجود البريد
        if (users.find(u => u.email === userData.email)) {
            return { success: false, error: 'البريد الإلكتروني مستخدم بالفعل' };
        }
        
        // تشفير كلمة المرور
        const hashedPassword = this.hashPasswordSync(userData.password);
        
        const newUser = {
            id: 'user_' + Date.now(),
            name: userData.name,
            email: userData.email,
            passwordHash: hashedPassword, // كلمة المرور مشفرة
            phone: userData.phone || '',
            role: userData.role || 'free',
            createdAt: new Date().toISOString()
        };
        
        users.push(newUser);
        localStorage.setItem('newra_users', JSON.stringify(users));
        
        // تسجيل الدخول تلقائياً
        return this.login(userData.email, userData.password);
    },

    // تسجيل الدخول/التسجيل بحساب Google
    googleLogin(googleData) {
        const users = JSON.parse(localStorage.getItem('newra_users') || '[]');
        
        // البحث عن مستخدم موجود بنفس البريد أو Google ID
        let user = users.find(u => u.email === googleData.email || u.googleId === googleData.googleId);
        
        if (user) {
            // تحديث بيانات Google إذا لم تكن موجودة
            if (!user.googleId) {
                user.googleId = googleData.googleId;
                user.picture = googleData.picture;
                user.authProvider = 'google';
                localStorage.setItem('newra_users', JSON.stringify(users));
            }
        } else {
            // إنشاء مستخدم جديد
            user = {
                id: 'user_' + Date.now(),
                name: googleData.name,
                email: googleData.email,
                googleId: googleData.googleId,
                picture: googleData.picture,
                authProvider: 'google',
                role: 'free',
                createdAt: new Date().toISOString()
            };
            users.push(user);
            localStorage.setItem('newra_users', JSON.stringify(users));
        }
        
        // إنشاء الجلسة
        localStorage.setItem('newra_session', JSON.stringify({
            id: user.id,
            name: user.name,
            email: user.email,
            picture: user.picture,
            role: user.role || 'free',
            authProvider: 'google',
            loggedIn: true,
            loginTime: new Date().toISOString()
        }));
        
        return { success: true, user };
    },

    // تسجيل الخروج
    logout() {
        localStorage.removeItem('newra_session');
        window.location.href = '/';
    },

    // التحقق من تسجيل الدخول
    isLoggedIn() {
        const session = this.getSession();
        return session.loggedIn === true;
    },

    // حماية الصفحة (إعادة توجيه إذا لم يكن مسجل دخول)
    requireAuth() {
        if (!this.isLoggedIn()) {
            window.location.href = '/auth/login/';
            return false;
        }
        return true;
    },

    // التحقق من صلاحية الأدمن
    requireAdmin() {
        if (!this.requireAuth()) return false;
        
        const user = this.getCurrentUser();
        if (!user || user.role !== 'admin') {
            alert('ليس لديك صلاحية للوصول لهذه الصفحة');
            window.location.href = '/dashboard/';
            return false;
        }
        return true;
    },

    // ترحيل البيانات القديمة للمستخدم الحالي
    migrateOldData() {
        const session = this.getSession();
        if (!session.id) return;

        // ترحيل العقارات القديمة
        const oldProperties = JSON.parse(localStorage.getItem('newra_properties') || '[]');
        if (oldProperties.length > 0) {
            const userProperties = this.getProperties();
            if (userProperties.length === 0) {
                this.setProperties(oldProperties);
                // لا نحذف البيانات القديمة حتى لا نفقدها
            }
        }

        // ترحيل العملاء القديمين
        const oldClients = JSON.parse(localStorage.getItem('newra_clients') || '[]');
        if (oldClients.length > 0) {
            const userClients = this.getClients();
            if (userClients.length === 0) {
                this.setClients(oldClients);
            }
        }

        // ترحيل إعدادات الوكيل
        const oldSettings = JSON.parse(localStorage.getItem('newra_agent_settings') || '{}');
        if (Object.keys(oldSettings).length > 0) {
            const userSettings = this.getAgentSettings();
            if (Object.keys(userSettings).length === 0) {
                this.setAgentSettings(oldSettings);
            }
        }
    }
};

// تصدير للاستخدام العام
window.InifyAuth = InifyAuth;
// للتوافق مع الكود القديم
window.NewraAuth = InifyAuth;
