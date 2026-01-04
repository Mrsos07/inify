# 🔧 حل مشكلة عدم ظهور QR Code في Evolution API

## المشكلة
عند إنشاء instance جديد في Evolution API، لا يظهر رمز QR Code المطلوب لربط الواتساب.

## ✅ الحل المطبق

### 1. تحديث Docker Compose Configuration

تم إضافة المتغيرات التالية في `docker-compose.evolution.yml`:

```yaml
environment:
  - CONFIG_SESSION_PHONE_VERSION=2.3000.1029340591  # ✅ الحل الأساسي
  - QRCODE_COLOR=#198754                             # لون QR Code
```

**السبب:** Evolution API يحتاج إلى إصدار واتساب محدث ومتوافق لتوليد QR Code بشكل صحيح.

---

## 🚀 خطوات تطبيق الحل

### الخطوة 1: إيقاف الخدمات الحالية

```bash
docker-compose -f docker-compose.evolution.yml down
```

### الخطوة 2: مسح البيانات القديمة (اختياري لكن موصى به)

```bash
# مسح الـ volumes القديمة
docker volume rm newra_evolution_data
docker volume rm newra_postgres_data

# أو مسح جميع البيانات
docker-compose -f docker-compose.evolution.yml down -v
```

### الخطوة 3: تشغيل الخدمات مع الإعدادات الجديدة

```bash
docker-compose -f docker-compose.evolution.yml up -d
```

### الخطوة 4: التحقق من تشغيل الخدمات

```bash
# مراقبة logs
docker-compose -f docker-compose.evolution.yml logs -f evolution-api

# التحقق من حالة الخدمات
docker-compose -f docker-compose.evolution.yml ps
```

---

## 🔍 التحقق من الحل

### 1. اختبار API

```bash
# التحقق من أن Evolution API يعمل
curl http://localhost:8080

# إنشاء instance جديد
curl -X POST http://localhost:8080/instance/create \
  -H "apikey: B6D711FCDE4D4FD5936544120E713976" \
  -H "Content-Type: application/json" \
  -d '{
    "instanceName": "test_instance",
    "integration": "WHATSAPP-BAILEYS",
    "qrcode": true
  }'

# الحصول على QR Code
curl http://localhost:8080/instance/connect/test_instance \
  -H "apikey: B6D711FCDE4D4FD5936544120E713976"
```

### 2. من خلال التطبيق

1. اذهب إلى صفحة إعدادات الوكيل
2. اضغط على "ربط الواتساب"
3. يجب أن يظهر QR Code بشكل صحيح الآن

---

## 📋 الإصدارات المتوافقة

| إصدار Evolution API | CONFIG_SESSION_PHONE_VERSION | الحالة |
|---------------------|------------------------------|---------|
| v2.1.1              | 2.3000.1020885143           | قديم    |
| v2.2.3              | 2.3000.1028178858           | مستقر   |
| v2.3.1+             | 2.3000.1029340591           | ✅ موصى به |

---

## 🛠️ حلول إضافية إذا استمرت المشكلة

### الحل 1: تحديث Evolution API

```bash
# تحديث الصورة
docker pull atendai/evolution-api:latest

# تعديل docker-compose.evolution.yml
# غيّر السطر:
# image: atendai/evolution-api:v2.2.3
# إلى:
# image: atendai/evolution-api:latest
```

### الحل 2: التحقق من Logs

```bash
# مراقبة logs بحثاً عن أخطاء
docker logs evolution-api --tail 100 -f
```

ابحث عن رسائل مثل:
- `QR Code generated successfully`
- `Connection state: open`
- أي أخطاء تتعلق بـ `baileys` أو `whatsapp`

### الحل 3: إعادة إنشاء Instance

من خلال التطبيق:
1. احذف الـ instance القديم
2. أنشئ instance جديد
3. استخدم `force_recreate=True` في الكود

```python
from services.whatsapp_service import whatsapp_service

result = whatsapp_service.create_instance(
    instance_name='new_instance',
    webhook_url='http://your-domain.com/webhooks/whatsapp/new_instance/',
    force_recreate=True  # ✅ يحذف القديم ويعيد الإنشاء
)
```

### الحل 4: التحقق من Network

تأكد من:
- المنفذ 8080 مفتوح ومتاح
- لا يوجد Firewall يحجب الاتصال
- Docker network يعمل بشكل صحيح

```bash
# اختبار الاتصال
curl http://localhost:8080
```

---

## 🎯 المتغيرات المهمة الأخرى

في `docker-compose.evolution.yml`:

```yaml
environment:
  # ✅ أساسي لظهور QR Code
  - CONFIG_SESSION_PHONE_VERSION=2.3000.1029340591
  
  # معلومات الجهاز المحاكى
  - CONFIG_SESSION_PHONE_CLIENT=Evolution
  - CONFIG_SESSION_PHONE_NAME=Chrome
  
  # إعدادات QR Code
  - QRCODE_LIMIT=30              # عدد محاولات QR Code
  - QRCODE_COLOR=#198754         # لون QR Code
  
  # Webhook events
  - WEBHOOK_EVENTS_QRCODE_UPDATED=true
  - WEBHOOK_EVENTS_CONNECTION_UPDATE=true
  
  # Logging
  - LOG_LEVEL=DEBUG              # للتشخيص
```

---

## 📊 الفرق بين الإعدادات

### قبل التحديث ❌
```yaml
environment:
  - CONFIG_SESSION_PHONE_CLIENT=Evolution
  - CONFIG_SESSION_PHONE_NAME=Chrome
  # ❌ لا يوجد CONFIG_SESSION_PHONE_VERSION
  - QRCODE_LIMIT=30
```

**النتيجة:** QR Code لا يظهر أو يظهر خطأ

### بعد التحديث ✅
```yaml
environment:
  - CONFIG_SESSION_PHONE_CLIENT=Evolution
  - CONFIG_SESSION_PHONE_NAME=Chrome
  - CONFIG_SESSION_PHONE_VERSION=2.3000.1029340591  # ✅ تم الإضافة
  - QRCODE_LIMIT=30
  - QRCODE_COLOR=#198754
```

**النتيجة:** QR Code يظهر بشكل صحيح

---

## 🔗 المراجع

- [Evolution API Documentation](https://doc.evolution-api.com/)
- [GitHub Issue #1768](https://github.com/EvolutionAPI/evolution-api/issues/1768)
- [WhatsApp Web Versions](https://web.whatsapp.com/check-update)

---

## ✅ الخلاصة

المشكلة كانت في عدم تحديد إصدار واتساب الذي يحاكيه Evolution API. الحل:

1. ✅ إضافة `CONFIG_SESSION_PHONE_VERSION=2.3000.1029340591`
2. ✅ إعادة تشغيل Docker containers
3. ✅ مسح البيانات القديمة إذا لزم الأمر
4. ✅ إنشاء instance جديد

الآن QR Code يجب أن يظهر بشكل صحيح! 🎉

---

**آخر تحديث:** 2026-01-04
**الحالة:** ✅ تم الحل
