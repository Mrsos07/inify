#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
# 🚀 Inify - Render Build Script
# ═══════════════════════════════════════════════════════════
# This script runs during Render deployment

set -o errexit  # Exit on error

echo "═══════════════════════════════════════════════════════════"
echo "🚀 Inify Build Script Starting..."
echo "═══════════════════════════════════════════════════════════"

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Run migrations
echo "🗄️ Running database migrations..."
python manage.py migrate --noinput

echo "═══════════════════════════════════════════════════════════"
echo "✅ Build completed successfully!"
echo "═══════════════════════════════════════════════════════════"
