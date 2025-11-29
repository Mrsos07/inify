/**
 * Newra Authentication & Authorization System
 * نظام المصادقة والصلاحيات
 */

const InifyAuth = {
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
            name: 'مؤسسة عقارية',
            nameEn: 'Agency',
            maxProperties: 100,
            maxClients: 500,
            canUseAI: true,
            canExportData: true,
            canViewAnalytics: true,
            canManageUsers: false,
            canCustomizeChatbot: true,
            canUseAdvancedRAG: true,
            canAddTeamMembers: true,
            maxTeamMembers: 10,
            canAccessAPI: true,
            canWhiteLabel: false,
            monthlyPrice: 499,
            badge: '🏢',
            color: '#6BB8C9'
        },
        marketer: {
            name: 'مسوق عقاري',
            nameEn: 'Marketer',
            maxProperties: 25,
            maxClients: 100,
            canUseAI: true,
            canExportData: true,
            canViewAnalytics: true,
            canManageUsers: false,
            canCustomizeChatbot: true,
            canUseAdvancedRAG: false,
            canAddTeamMembers: false,
            maxTeamMembers: 0,
            canAccessAPI: false,
            canWhiteLabel: false,
            monthlyPrice: 149,
            badge: '💼',
            color: '#4A90A4'
        },
        free: {
            name: 'مستخدم مجاني',
            nameEn: 'Free User',
            maxProperties: 3,
            maxClients: 10,
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

    // تسجيل الدخول
    login(email, password) {
        const users = JSON.parse(localStorage.getItem('newra_users') || '[]');
        const user = users.find(u => u.email === email && u.password === password);
        
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

    // تسجيل مستخدم جديد
    register(userData) {
        const users = JSON.parse(localStorage.getItem('newra_users') || '[]');
        
        // التحقق من عدم وجود البريد
        if (users.find(u => u.email === userData.email)) {
            return { success: false, error: 'البريد الإلكتروني مستخدم بالفعل' };
        }
        
        const newUser = {
            id: 'user_' + Date.now(),
            name: userData.name,
            email: userData.email,
            password: userData.password,
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
            window.location.href = '/login/';
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
