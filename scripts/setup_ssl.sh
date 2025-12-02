#!/bin/bash
# ═══════════════════════════════════════════════════════════
# 🔒 Inify - SSL Certificate Setup (Let's Encrypt)
# ═══════════════════════════════════════════════════════════

set -e

DOMAIN="inify.sa"
EMAIL="admin@inify.sa"

echo "═══════════════════════════════════════════════════════════"
echo "🔒 Setting up SSL Certificate for $DOMAIN"
echo "═══════════════════════════════════════════════════════════"

# Install Certbot
echo "📦 Installing Certbot..."
sudo apt update
sudo apt install -y certbot python3-certbot-nginx

# Get certificate
echo "🔐 Obtaining SSL certificate..."
sudo certbot --nginx \
    -d $DOMAIN \
    -d www.$DOMAIN \
    --non-interactive \
    --agree-tos \
    --email $EMAIL \
    --redirect

# Setup auto-renewal
echo "⏰ Setting up auto-renewal..."
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Test renewal
echo "🧪 Testing renewal..."
sudo certbot renew --dry-run

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ SSL Certificate installed successfully!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Certificate location: /etc/letsencrypt/live/$DOMAIN/"
echo "Auto-renewal: Enabled (runs twice daily)"
echo ""
