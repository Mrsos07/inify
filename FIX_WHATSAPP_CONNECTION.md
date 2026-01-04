# 🔧 حل مشكلة عدم اكتمال ربط الواتساب

## المشكلة
بعد مسح QR Code، يبقى Instance في حالة "Connecting" ولا يتم الاتصال بشكل صحيح.

## السبب
من logs Evolution API:
- ❌ `stream:error code 401` - device_removed (الجهاز تم إزالته)
- ❌ `stream:error code 515` - خطأ في الاتصال
- ❌ `Timed Out` - فشل keep alive

## الحل الكامل

### الخطوة 1: مسح البيانات القديمة

```bash
# إيقاف Evolution API
docker-compose -f docker-compose.evolution.yml down

# مسح volumes القديمة (البيانات المخزنة)
docker volume rm newra_evolution_data
docker volume rm newra_postgres_data

# أو مسح كل شيء
docker-compose -f docker-compose.evolution.yml down -v
```

### الخطوة 2: تشغيل Evolution API من جديد

```bash
docker-compose -f docker-compose.evolution.yml up -d
```

### الخطوة 3: انتظر حتى يجهز Evolution API

```bash
# راقب logs حتى ترى "Listening on TCP"
docker logs evolution-api -f
```

### الخطوة 4: حذف Instances القديمة من Django

افتح Django shell:
```bash
python manage.py shell
```

ثم نفذ:
```python
from apps.agents.models import WhatsAppInstance
# حذف جميع instances القديمة
WhatsAppInstance.objects.all().delete()
print("✅ تم حذف جميع instances القديمة")
exit()
```

### الخطوة 5: جرب الربط من جديد

1. اذهب إلى Dashboard
2. اضغط "ربط واتساب"
3. امسح QR Code **فوراً** (خلال 30 ثانية)
4. انتظر 5-10 ثوانٍ
5. يجب أن يتصل بنجاح ✅

---

## نصائح مهمة

### ✅ افعل:
- امسح QR Code بسرعة (خلال 30 ثانية من ظهوره)
- تأكد من أن Evolution API يعمل قبل المحاولة
- استخدم رقم واتساب نظيف (غير مربوط بأي جهاز آخر)
- راقب logs في Console (F12)

### ❌ لا تفعل:
- لا تمسح QR Code بعد انتهاء صلاحيته (30 ثانية)
- لا تحاول الربط عدة مرات بسرعة
- لا تستخدم رقم مربوط بـ WhatsApp Web آخر
- لا تغلق الصفحة أثناء الربط

---

## التشخيص

### تحقق من حالة Evolution API:
```bash
# حالة الخدمات
docker-compose -f docker-compose.evolution.yml ps

# logs مباشرة
docker logs evolution-api -f

# اختبار API
curl http://localhost:8080
```

### تحقق من Django:
```bash
# حالة instances في قاعدة البيانات
python manage.py shell
>>> from apps.agents.models import WhatsAppInstance
>>> for i in WhatsAppInstance.objects.all():
...     print(f"{i.instance_name}: {i.status}")
>>> exit()
```

### تحقق من Webhook:
```bash
# راقب webhook logs
tail -f webhook_debug.log
```

---

## الأخطاء الشائعة وحلولها

### خطأ: "stream:error code 401"
**السبب:** الجلسة انتهت أو الجهاز تم إزالته
**الحل:** امسح البيانات وأعد المحاولة (الخطوات 1-5)

### خطأ: "stream:error code 515"
**السبب:** مشكلة في الاتصال بخوادم واتساب
**الحل:** 
- تحقق من الإنترنت
- أعد تشغيل Evolution API
- جرب رقم واتساب آخر

### خطأ: "Timed Out - keep alive"
**السبب:** Evolution API لا يستطيع الحفاظ على الاتصال
**الحل:**
- تحقق من موارد النظام (RAM, CPU)
- أعد تشغيل Docker
- قلل عدد instances المفتوحة

### خطأ: "Instance not found"
**السبب:** Instance تم حذفه من Evolution API لكن موجود في Django
**الحل:**
```python
# حذف instance من Django
python manage.py shell
>>> from apps.agents.models import WhatsAppInstance
>>> WhatsAppInstance.objects.filter(instance_name='اسم_instance').delete()
```

---

## معلومات إضافية

### عمر QR Code
- QR Code صالح لمدة **30 ثانية** فقط
- بعد 30 ثانية، يجب طلب QR جديد
- امسح الباركود فوراً عند ظهوره

### حالات Instance
- `connecting` - جاري الاتصال
- `qr_ready` - QR Code جاهز للمسح
- `connected` - متصل بنجاح ✅
- `disconnected` - غير متصل

### Webhook Events
- `qrcode.updated` - QR Code جديد
- `connection.update` - تحديث حالة الاتصال
- `messages.upsert` - رسالة جديدة

---

## الخلاصة

المشكلة الرئيسية كانت في:
1. ✅ بيانات قديمة في Evolution API
2. ✅ Timeout في keep alive connection
3. ✅ Stream errors (401, 515)

الحل:
1. ✅ مسح البيانات القديمة
2. ✅ إعادة تشغيل Evolution API
3. ✅ حذف instances القديمة من Django
4. ✅ محاولة الربط من جديد

---

**تم التحديث:** 2026-01-04
**الحالة:** ✅ جاهز للتطبيق
