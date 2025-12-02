# 🚀 Inify - Render Deployment Guide

## خطوات النشر على Render.com

### 1. إنشاء حساب على Render
- اذهب إلى [render.com](https://render.com)
- سجل بحساب GitHub

### 2. ربط المستودع
1. اضغط **New +** → **Web Service**
2. اختر **Build and deploy from a Git repository**
3. اربط مستودع GitHub الخاص بالمشروع

### 3. إعدادات الخدمة
```
Name: inify
Region: Frankfurt (EU Central)
Branch: main
Runtime: Docker
```

### 4. Environment Variables (مهم جداً!)

أضف هذه المتغيرات في **Environment** tab:

| Variable | Value |
|----------|-------|
| `DEBUG` | `False` |
| `DJANGO_SECRET_KEY` | (اضغط Generate) |
| `ALLOWED_HOSTS` | `inify.ai,www.inify.ai,.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://inify.ai,https://www.inify.ai,https://*.onrender.com` |
| `GEMINI_API_KEY` | (مفتاح Gemini API الخاص بك) |
| `ADMIN_SECRET_KEY` | (اضغط Generate) |
| `FIELD_ENCRYPTION_KEY` | (انسخ من .env.production) |

### 5. إنشاء قاعدة البيانات
1. اضغط **New +** → **PostgreSQL**
2. الإعدادات:
   - Name: `inify-db`
   - Region: Frankfurt
   - Plan: Starter (أو Standard للإنتاج)

3. بعد الإنشاء، انسخ **Internal Database URL**
4. أضفه كـ `DATABASE_URL` في Web Service

### 6. ربط الدومين المخصص
1. اذهب إلى **Settings** → **Custom Domains**
2. أضف: `inify.ai` و `www.inify.ai`
3. أضف DNS Records في مزود الدومين:
   ```
   Type: CNAME
   Name: @
   Value: [your-service].onrender.com
   
   Type: CNAME
   Name: www
   Value: [your-service].onrender.com
   ```

### 7. SSL Certificate
- Render يوفر SSL مجاني تلقائياً! ✅

---

## 🔧 أوامر مفيدة

### الوصول للـ Shell
```bash
# من Render Dashboard → Shell tab
python manage.py createsuperuser
python manage.py migrate
```

### مشاهدة Logs
```bash
# من Render Dashboard → Logs tab
```

---

## ✅ Checklist قبل النشر

- [ ] `GEMINI_API_KEY` مضاف
- [ ] `DATABASE_URL` مربوط
- [ ] `DJANGO_SECRET_KEY` مُولّد
- [ ] DNS Records مضافة
- [ ] SSL Certificate فعّال

---

## 🎉 بعد النشر

1. اذهب إلى: `https://inify.ai/admin-panel/`
2. سجل دخول بـ `ADMIN_SECRET_KEY`
3. أضف إعدادات الوكيل الذكي
4. جرب الشات!

---

## 📞 الدعم

إذا واجهت مشاكل:
1. تحقق من **Logs** في Render Dashboard
2. تأكد من أن كل Environment Variables مضافة
3. تأكد من أن قاعدة البيانات متصلة
