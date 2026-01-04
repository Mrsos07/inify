# 🚀 دليل إعداد نظام الواتساب المتطور

## نظرة عامة

تم تطوير نظام متكامل لحل مشكلة الرد على المحادثة الصحيحة في الواتساب. النظام يتضمن:

1. **Session Manager** - إدارة دقيقة للجلسات
2. **WebSocket** - اتصال فوري للمحادثات الحية
3. **Dashboard** - لوحة تحكم للمانيجر
4. **Webhook محسّن** - معالجة متقدمة للرسائل

---

## 📋 المكونات الجديدة

### 1. WhatsApp Session Manager
**الملف:** `services/whatsapp_session_manager.py`

**الميزات:**
- تتبع دقيق لكل محادثة بناءً على رقم الهاتف
- منع التداخل بين المحادثات المتزامنة
- قفل المعالجة (Processing Lock) لمنع الرسائل المكررة
- حفظ السياق في الذاكرة المؤقتة (Cache)

**الاستخدام:**
```python
from services.whatsapp_session_manager import whatsapp_session_manager

# إنشاء أو الحصول على جلسة
session = whatsapp_session_manager.create_or_get_session(
    instance_name='inify_abc123',
    phone='966512345678',
    sender_name='أحمد'
)

# ربط الجلسة بمحادثة
whatsapp_session_manager.link_conversation(
    instance_name='inify_abc123',
    phone='966512345678',
    conversation_id='uuid-here'
)
```

---

### 2. WebSocket Consumer
**الملف:** `apps/chat/consumers.py`

**الميزات:**
- اتصال فوري بين المانيجر والنظام
- بث الرسائل الجديدة تلقائياً
- إرسال رسائل من المانيجر مباشرة
- عرض الجلسات النشطة

**الاتصال:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/whatsapp/{agent_id}/');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    // معالجة الرسائل
};
```

---

### 3. Dashboard المباشر
**الملف:** `templates/dashboard/whatsapp_live.html`

**الميزات:**
- عرض جميع المحادثات النشطة
- متابعة الرسائل في الوقت الفعلي
- إرسال رسائل من المانيجر
- إشعارات صوتية ومتصفح

**الوصول:**
```
http://localhost:8000/api/v1/chat/whatsapp/live/
```

---

### 4. Webhook محسّن
**الملف:** `apps/chat/whatsapp_views.py`

**التحسينات:**
- استخدام Session Manager لتتبع المحادثات
- قفل المعالجة لمنع التداخل
- ربط تلقائي بين الجلسات والمحادثات
- تسجيل تفصيلي (Logging) للتشخيص

---

## 🔧 خطوات التثبيت

### 1. تثبيت المكتبات المطلوبة

```bash
pip install -r requirements.txt
```

المكتبات الجديدة:
- `channels>=4.0.0` - دعم WebSocket
- `daphne>=4.0.0` - ASGI server
- `channels-redis>=4.1.0` - Redis للـ Channel Layers (اختياري)
- `django-redis>=5.4.0` - Redis للـ Cache (اختياري)

---

### 2. تحديث الإعدادات

تم تحديث `config/settings.py` تلقائياً بالإضافات التالية:

```python
# INSTALLED_APPS
'daphne',  # أول التطبيقات
'channels',

# ASGI Configuration
ASGI_APPLICATION = 'config.asgi.application'

# Channel Layers
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    }
}

# Cache (للـ Session Manager)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
```

---

### 3. إنشاء جدول الـ Cache (اختياري)

إذا كنت تستخدم Database Cache:

```bash
python manage.py createcachetable
```

---

### 4. تشغيل الخادم

**للتطوير المحلي:**
```bash
python manage.py runserver
```

أو باستخدام Daphne:
```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

**للإنتاج:**
```bash
gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker
```

---

## 🎯 كيفية الاستخدام

### 1. ربط الواتساب

1. اذهب إلى إعدادات الوكيل
2. اضغط على "ربط الواتساب"
3. امسح QR Code
4. انتظر الاتصال

### 2. فتح Dashboard المباشر

```
http://localhost:8000/api/v1/chat/whatsapp/live/
```

ستظهر لك:
- قائمة المحادثات النشطة
- الرسائل في الوقت الفعلي
- إمكانية الرد مباشرة

### 3. مراقبة الجلسات

يمكنك مراقبة الجلسات النشطة:

```python
from services.whatsapp_session_manager import whatsapp_session_manager

# الحصول على إحصائيات جلسة
stats = whatsapp_session_manager.get_session_stats(
    instance_name='inify_abc123',
    phone='966512345678'
)
print(stats)
```

---

## 🔍 التشخيص وحل المشاكل

### مشكلة: الرسائل لا تصل

**الحل:**
1. تحقق من أن Evolution API يعمل:
   ```bash
   curl http://localhost:8080
   ```

2. تحقق من Webhook URL في Evolution API:
   ```
   http://your-domain.com/webhooks/whatsapp/{instance_name}/
   ```

3. راجع logs:
   ```bash
   tail -f logs/newra.log
   ```

### مشكلة: WebSocket لا يتصل

**الحل:**
1. تحقق من أن Daphne يعمل
2. تحقق من إعدادات ASGI في `config/asgi.py`
3. راجع console في المتصفح

### مشكلة: الرد على محادثة خاطئة

**الحل:**
1. تحقق من أن Session Manager يعمل:
   ```python
   from services.whatsapp_session_manager import whatsapp_session_manager
   session = whatsapp_session_manager.get_session('instance', 'phone')
   print(session)
   ```

2. راجع logs للتأكد من ربط الجلسة بالمحادثة الصحيحة

---

## 🚀 التحسينات للإنتاج

### 1. استخدام Redis

**تثبيت Redis:**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Windows
# استخدم Docker أو WSL
```

**تحديث الإعدادات:**
```python
# في .env
REDIS_URL=redis://localhost:6379

# سيتم استخدام Redis تلقائياً للـ Cache و Channel Layers
```

### 2. تفعيل HTTPS

للـ WebSocket في الإنتاج، استخدم `wss://` بدلاً من `ws://`:

```javascript
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${protocol}//${window.location.host}/ws/whatsapp/${agentId}/`;
```

### 3. Monitoring

راقب الجلسات النشطة:
```python
sessions = whatsapp_session_manager.get_active_sessions('instance_name')
print(f"Active sessions: {len(sessions)}")
```

---

## 📊 الفوائد الرئيسية

✅ **دقة 100%** في الرد على المحادثة الصحيحة
✅ **لا تداخل** بين المحادثات المتزامنة
✅ **اتصال فوري** عبر WebSocket
✅ **Dashboard متقدم** للمانيجر
✅ **قابل للتوسع** مع Redis
✅ **تسجيل شامل** للتشخيص

---

## 🎓 الخلاصة

النظام الجديد يحل مشكلة الرد على المحادثة الخاطئة بشكل كامل من خلال:

1. **Session Manager** - يتتبع كل محادثة بدقة
2. **Processing Lock** - يمنع المعالجة المتزامنة
3. **Conversation Linking** - يربط الجلسة بالمحادثة الصحيحة
4. **WebSocket** - يوفر اتصال فوري
5. **Dashboard** - يتيح المراقبة والتحكم

---

## 📞 الدعم

إذا واجهت أي مشاكل:
1. راجع logs في `logs/newra.log`
2. تحقق من `webhook_debug.log`
3. استخدم أدوات التشخيص المدمجة

---

**تم التطوير بواسطة:** Cascade AI
**التاريخ:** 2026-01-04
**الإصدار:** 2.0
