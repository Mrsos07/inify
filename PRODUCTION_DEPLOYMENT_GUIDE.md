# 🚀 دليل نشر Inify على الإنتاج (inify.ai)

## 📋 المتطلبات الأساسية

### 1. الخادم
- **نظام التشغيل:** Ubuntu 22.04 LTS أو أحدث
- **المعالج:** 2 CPU cores (4 موصى به)
- **الذاكرة:** 4GB RAM (8GB موصى به)
- **التخزين:** 50GB SSD
- **النطاق:** inify.ai (مع DNS مُعد)

### 2. البرمجيات المطلوبة
```bash
# تحديث النظام
sudo apt update && sudo apt upgrade -y

# تثبيت Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip -y

# تثبيت PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# تثبيت Docker & Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt install docker-compose -y

# تثبيت Nginx
sudo apt install nginx -y

# تثبيت Certbot (للـ SSL)
sudo apt install certbot python3-certbot-nginx -y
```

---

## 🔐 الخطوة 1: تأمين الخادم

### إعداد Firewall
```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### إنشاء مستخدم للتطبيق
```bash
sudo adduser inify
sudo usermod -aG sudo inify
sudo usermod -aG docker inify
su - inify
```

---

## 📦 الخطوة 2: إعداد قاعدة البيانات

### PostgreSQL Setup
```bash
sudo -u postgres psql

-- في PostgreSQL shell:
CREATE DATABASE inify_production;
CREATE USER inify_user WITH PASSWORD 'your-strong-password';
ALTER ROLE inify_user SET client_encoding TO 'utf8';
ALTER ROLE inify_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE inify_user SET timezone TO 'Asia/Riyadh';
GRANT ALL PRIVILEGES ON DATABASE inify_production TO inify_user;
\q
```

---

## 🔑 الخطوة 3: إعداد المتغيرات البيئية

### إنشاء ملف .env
```bash
cd /home/inify
git clone https://github.com/your-repo/inify.git
cd inify

# نسخ ملف البيئة
cp .env.production.secure .env

# تعديل المتغيرات
nano .env
```

### توليد المفاتيح السرية
```bash
# Django SECRET_KEY
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Fernet Encryption Key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Evolution API Key
openssl rand -hex 32
```

---

## 🐳 الخطوة 4: إعداد Evolution API

### تحديث docker-compose
```bash
# نسخ ملف الإنتاج
cp docker-compose.production.yml docker-compose.yml

# تعديل المتغيرات
nano docker-compose.yml
```

### تشغيل Evolution API
```bash
docker-compose up -d

# التحقق من الحالة
docker-compose ps
docker-compose logs -f evolution-api
```

---

## 🌐 الخطوة 5: إعداد Django

### إنشاء Virtual Environment
```bash
python3.11 -m venv venv
source venv/bin/activate
```

### تثبيت المتطلبات
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### تشغيل Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### إنشاء Superuser
```bash
python manage.py createsuperuser
```

### جمع الملفات الثابتة
```bash
python manage.py collectstatic --noinput
```

---

## 🔒 الخطوة 6: إعداد SSL (HTTPS)

### الحصول على شهادة Let's Encrypt
```bash
sudo certbot --nginx -d inify.ai -d www.inify.ai
```

### تجديد تلقائي
```bash
sudo certbot renew --dry-run
```

---

## ⚙️ الخطوة 7: إعداد Nginx

### إنشاء ملف الإعداد
```bash
sudo nano /etc/nginx/sites-available/inify.ai
```

```nginx
# Inify Production Configuration
upstream django_app {
    server 127.0.0.1:8000;
}

upstream evolution_api {
    server 127.0.0.1:8080;
}

# HTTP -> HTTPS Redirect
server {
    listen 80;
    listen [::]:80;
    server_name inify.ai www.inify.ai;
    return 301 https://$server_name$request_uri;
}

# HTTPS Server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name inify.ai www.inify.ai;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/inify.ai/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/inify.ai/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Client Max Body Size
    client_max_body_size 20M;

    # Static Files
    location /static/ {
        alias /home/inify/inify/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media Files
    location /media/ {
        alias /home/inify/inify/media/;
        expires 7d;
    }

    # Evolution API Proxy
    location /evolution/ {
        proxy_pass http://evolution_api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Django Application
    location / {
        proxy_pass http://django_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # WebSocket Support
    location /ws/ {
        proxy_pass http://django_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```

### تفعيل الموقع
```bash
sudo ln -s /etc/nginx/sites-available/inify.ai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🚀 الخطوة 8: إعداد Gunicorn

### إنشاء ملف systemd service
```bash
sudo nano /etc/systemd/system/inify.service
```

```ini
[Unit]
Description=Inify Django Application
After=network.target postgresql.service

[Service]
Type=notify
User=inify
Group=www-data
WorkingDirectory=/home/inify/inify
Environment="PATH=/home/inify/inify/venv/bin"
ExecStart=/home/inify/inify/venv/bin/gunicorn \
    --workers 4 \
    --worker-class gthread \
    --threads 2 \
    --timeout 120 \
    --bind 127.0.0.1:8000 \
    --access-logfile /home/inify/inify/logs/access.log \
    --error-logfile /home/inify/inify/logs/error.log \
    --log-level info \
    config.wsgi:application

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### تفعيل الخدمة
```bash
# إنشاء مجلد logs
mkdir -p /home/inify/inify/logs

# تفعيل وتشغيل
sudo systemctl daemon-reload
sudo systemctl enable inify
sudo systemctl start inify
sudo systemctl status inify
```

---

## 📊 الخطوة 9: المراقبة والصيانة

### إعداد Logrotate
```bash
sudo nano /etc/logrotate.d/inify
```

```
/home/inify/inify/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 inify www-data
    sharedscripts
    postrotate
        systemctl reload inify > /dev/null 2>&1 || true
    endscript
}
```

### مراقبة الخدمات
```bash
# Django
sudo systemctl status inify
sudo journalctl -u inify -f

# Nginx
sudo systemctl status nginx
sudo tail -f /var/log/nginx/error.log

# Evolution API
docker-compose logs -f evolution-api

# PostgreSQL
sudo systemctl status postgresql
```

---

## 🔄 الخطوة 10: النسخ الاحتياطي

### إعداد Database Backup
```bash
# إنشاء سكريبت backup
nano /home/inify/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/home/inify/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="inify_production"

mkdir -p $BACKUP_DIR

# Database backup
pg_dump -U inify_user $DB_NAME | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Media files backup
tar -czf $BACKUP_DIR/media_$DATE.tar.gz /home/inify/inify/media/

# Keep only last 7 days
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
```

```bash
chmod +x /home/inify/backup.sh

# إضافة إلى cron (يومياً الساعة 2 صباحاً)
crontab -e
0 2 * * * /home/inify/backup.sh >> /home/inify/backup.log 2>&1
```

---

## ✅ الخطوة 11: اختبار النشر

### Checklist
- [ ] الموقع يعمل على https://inify.ai
- [ ] SSL certificate صحيح
- [ ] تسجيل الدخول يعمل
- [ ] Google OAuth يعمل
- [ ] WhatsApp integration يعمل
- [ ] رفع الملفات يعمل
- [ ] الأداء جيد (< 2s load time)
- [ ] لا توجد أخطاء في logs

### أدوات الاختبار
```bash
# SSL Test
curl -I https://inify.ai

# Performance Test
ab -n 100 -c 10 https://inify.ai/

# Security Headers
curl -I https://inify.ai | grep -i "security\|x-frame\|x-content"
```

---

## 🆘 استكشاف الأخطاء

### Django لا يعمل
```bash
sudo systemctl restart inify
sudo journalctl -u inify -n 50
```

### Evolution API لا يعمل
```bash
docker-compose restart evolution-api
docker-compose logs evolution-api
```

### مشاكل SSL
```bash
sudo certbot renew --force-renewal
sudo systemctl restart nginx
```

### مشاكل Database
```bash
sudo systemctl restart postgresql
sudo -u postgres psql -c "SELECT version();"
```

---

## 📞 الدعم

- **Documentation:** https://docs.inify.ai
- **Support:** support@inify.ai
- **Emergency:** +966-XXX-XXXX

---

## 🎉 تم النشر بنجاح!

موقعك الآن يعمل على: **https://inify.ai** 🚀
