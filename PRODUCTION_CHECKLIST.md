# 🚀 Inify - Production Deployment Checklist

## ✅ قبل الرفع على السيرفر

### 1. إعدادات البيئة (.env)

```bash
# توليد SECRET_KEY قوي
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# توليد FIELD_ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**ملف .env للإنتاج:**
```env
# Django
DJANGO_SECRET_KEY=your-generated-50-char-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database (PostgreSQL)
USE_POSTGRES=True
DB_NAME=inify_production
DB_USER=inify_user
DB_PASSWORD=strong-password-here
DB_HOST=localhost
DB_PORT=5432

# Security
ADMIN_SECRET_KEY=strong-admin-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=strong-admin-password
FIELD_ENCRYPTION_KEY=your-generated-fernet-key

# API Keys
GEMINI_API_KEY=your-gemini-api-key

# CORS (أضف دومينك)
CORS_ALLOWED_ORIGINS=https://yourdomain.com
```

---

### 2. أوامر التجهيز

```bash
# 1. تثبيت المتطلبات
pip install -r requirements.txt

# 2. جمع الملفات الثابتة
python manage.py collectstatic --noinput

# 3. تطبيق الـ migrations
python manage.py migrate

# 4. إنشاء superuser
python manage.py createsuperuser

# 5. فحص الأمان
python manage.py check --deploy
```

---

### 3. إعداد Gunicorn

**ملف `gunicorn.conf.py`:**
```python
bind = "0.0.0.0:8000"
workers = 3
worker_class = "sync"
timeout = 120
keepalive = 5
errorlog = "/var/log/gunicorn/error.log"
accesslog = "/var/log/gunicorn/access.log"
loglevel = "info"
```

**تشغيل:**
```bash
gunicorn config.wsgi:application -c gunicorn.conf.py
```

---

### 4. إعداد Nginx

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location /static/ {
        alias /path/to/inify/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /path/to/inify/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

### 5. SSL Certificate (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

---

### 6. Systemd Service

**ملف `/etc/systemd/system/inify.service`:**
```ini
[Unit]
Description=Inify Gunicorn Daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/inify
ExecStart=/path/to/inify/venv/bin/gunicorn config.wsgi:application -c gunicorn.conf.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable inify
sudo systemctl start inify
```

---

## 🔒 فحص الأمان النهائي

```bash
# يجب أن يكون الناتج: 0 issues
python manage.py check --deploy
```

---

## 📊 مراقبة الأداء

### Logs
```bash
# Django logs
tail -f /path/to/inify/logs/newra.log

# Gunicorn logs
tail -f /var/log/gunicorn/error.log

# Nginx logs
tail -f /var/log/nginx/error.log
```

---

## ✅ الموقع جاهز للإنتاج عند:

- [ ] `DEBUG=False` في .env
- [ ] `SECRET_KEY` قوي (50+ حرف)
- [ ] `ALLOWED_HOSTS` يحتوي الدومين
- [ ] PostgreSQL مُعد
- [ ] SSL Certificate مُثبت
- [ ] Nginx مُعد
- [ ] Gunicorn يعمل
- [ ] `python manage.py check --deploy` = 0 issues
- [ ] Backup strategy موجودة

---

## 🎉 تهانينا!

الموقع مُعد بشكل ممتاز للإنتاج. كل إعدادات الأمان موجودة وتُفعّل تلقائياً عند `DEBUG=False`.
