# 🏠 Newra Estate AI

<p align="center">
  <img src="static/images/logo.png" alt="Newra Logo" width="200">
</p>

<h3 align="center">The New Era of Intelligence</h3>

<p align="center">
  وكيل ذكاء اصطناعي عقاري متكامل لمساعدة المسوقين العقاريين في بيع وتأجير العقارات
</p>

---

## 🌟 المميزات

- **محادثة ذكية**: وكيل AI يتحدث بالعربية والإنجليزية بأسلوب مهني وودود
- **بحث متقدم**: بحث في العقارات بناءً على تفضيلات العميل
- **إدارة العملاء**: تحويل المحادثات إلى عملاء محتملين (Leads)
- **جدولة المعاينات**: حجز مواعيد معاينة العقارات
- **تكامل n8n**: إرسال الإشعارات والبيانات عبر Webhooks
- **واجهة شات قابلة للتضمين**: Widget جاهز للتضمين في أي موقع

## 🚀 البدء السريع

### المتطلبات

- Python 3.10+
- PostgreSQL 14+
- OpenAI API Key

### التثبيت

```bash
# استنساخ المشروع
git clone https://github.com/your-repo/newra-estate.git
cd newra-estate

# إنشاء بيئة افتراضية
python -m venv venv
source venv/bin/activate  # Linux/Mac
# أو
.\venv\Scripts\activate  # Windows

# تثبيت التبعيات
pip install -r requirements.txt

# نسخ ملف البيئة
cp .env.example .env
# قم بتعديل .env بإعداداتك

# تشغيل الترحيلات
python manage.py migrate

# إنشاء مستخدم مدير
python manage.py createsuperuser

# تشغيل الخادم
python manage.py runserver
```

## 📁 هيكل المشروع

```
Newra/
├── apps/
│   ├── agents/          # إدارة المسوقين العقاريين
│   ├── chat/            # المحادثات والرسائل
│   ├── leads/           # العملاء المحتملين
│   └── properties/      # العقارات
├── config/              # إعدادات Django
├── prompts/             # System Prompts للـ AI
├── services/            # خدمات الأعمال
├── static/              # الملفات الثابتة
├── templates/           # قوالب HTML
└── manage.py
```

## 🔌 API Endpoints

### المحادثات
- `POST /api/v1/chat/public/` - إرسال رسالة (عام)
- `GET /api/v1/chat/conversations/` - قائمة المحادثات
- `POST /api/v1/chat/conversations/{id}/send_message/` - إرسال رسالة

### العقارات
- `GET /api/v1/properties/` - قائمة العقارات
- `POST /api/v1/properties/search/` - بحث متقدم
- `GET /api/v1/properties/{id}/` - تفاصيل عقار

### العملاء المحتملين
- `GET /api/v1/leads/` - قائمة العملاء
- `POST /api/v1/leads/{id}/update_status/` - تحديث الحالة
- `GET /api/v1/leads/statistics/` - إحصائيات

### Webhooks
- `POST /webhooks/chat/` - استقبال رسائل من n8n/WhatsApp

## 🎨 تضمين Widget الشات

```html
<!-- أضف هذا الكود في موقعك -->
<script>
  window.NEWRA_CHAT_CONFIG = {
    agentId: 'YOUR_AGENT_ID',
    apiUrl: 'https://your-api.com/api/v1/chat/public/',
    botName: 'مساعد العقارات',
    language: 'ar'
  };
</script>
<script src="https://your-api.com/static/js/chat-widget.js"></script>
```

## 🔧 إعدادات AI

يمكنك تخصيص سلوك الـ AI من خلال:

1. **System Prompt**: تعديل `prompts/system_prompt.py`
2. **إعدادات المسوق**: من لوحة التحكم
3. **متغيرات البيئة**: `AI_MODEL`, `AI_TEMPERATURE`, `AI_MAX_TOKENS`

## 📊 لوحة التحكم

الوصول إلى لوحة التحكم: `http://localhost:8000/admin/`

## 🔐 الأمان

- لا يتم تخزين بيانات حساسة في الكود
- جميع الاتصالات مشفرة
- التحقق من صحة Webhook عبر Secret Key
- فصل بيانات كل مسوق عن الآخر

## 📝 الترخيص

© 2024 Newra - The New Era of Intelligence. جميع الحقوق محفوظة.

---

<p align="center">
  Made with ❤️ by Newra Team
</p>
