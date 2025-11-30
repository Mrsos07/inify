/**
 * Inify Configuration - EXAMPLE FILE
 * ===================================
 * 
 * ⚠️ هذا ملف مثال فقط!
 * 
 * للاستخدام:
 * 1. انسخ هذا الملف وسمه config.js
 * 2. أضف مفاتيح API الخاصة بك
 * 3. لا ترفع config.js على GitHub (موجود في .gitignore)
 * 
 * 🔒 ملاحظة أمنية:
 * - لا تشارك هذا الملف مع أي شخص
 * - لا ترفعه على أي repository عام
 */

const CONFIG = {
    // ═══════════════════════════════════════
    // 🤖 Gemini AI API
    // ═══════════════════════════════════════
    // احصل على مفتاح من: https://aistudio.google.com/app/apikey
    GEMINI_API_KEY: 'YOUR_GEMINI_API_KEY_HERE',
    GEMINI_MODEL: 'gemini-2.5-pro-preview-05-06',
    
    // ═══════════════════════════════════════
    // 🔐 Google OAuth
    // ═══════════════════════════════════════
    // أنشئ مشروع في: https://console.cloud.google.com/
    // ثم فعّل Google+ API واحصل على Client ID
    GOOGLE_CLIENT_ID: 'YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com',
    
    // ═══════════════════════════════════════
    // ⚙️ App Settings
    // ═══════════════════════════════════════
    APP_NAME: 'Inify',
    APP_VERSION: '1.0.0'
};
