#!/bin/bash
# ═══════════════════════════════════════════════════════════
# 🚀 Inify - Production Deployment Script
# ═══════════════════════════════════════════════════════════

set -e  # Exit on error

echo "═══════════════════════════════════════════════════════════"
echo "🚀 Inify Production Deployment"
echo "═══════════════════════════════════════════════════════════"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project directory
PROJECT_DIR="/var/www/inify"
VENV_DIR="$PROJECT_DIR/venv"

# ─────────────────────────────────────────────────────────────
# 1. Update code
# ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}📥 Pulling latest code...${NC}"
cd $PROJECT_DIR
git pull origin main

# ─────────────────────────────────────────────────────────────
# 2. Activate virtual environment
# ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}🐍 Activating virtual environment...${NC}"
source $VENV_DIR/bin/activate

# ─────────────────────────────────────────────────────────────
# 3. Install dependencies
# ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}📦 Installing dependencies...${NC}"
pip install -r requirements.txt --quiet

# ─────────────────────────────────────────────────────────────
# 4. Run migrations
# ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}🗄️ Running migrations...${NC}"
python manage.py migrate --noinput

# ─────────────────────────────────────────────────────────────
# 5. Collect static files
# ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}📁 Collecting static files...${NC}"
python manage.py collectstatic --noinput --clear

# ─────────────────────────────────────────────────────────────
# 6. Security check
# ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}🔒 Running security check...${NC}"
python manage.py check --deploy

# ─────────────────────────────────────────────────────────────
# 7. Restart services
# ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}🔄 Restarting services...${NC}"
sudo systemctl restart inify
sudo systemctl restart nginx

# ─────────────────────────────────────────────────────────────
# 8. Check status
# ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}📊 Checking service status...${NC}"
sudo systemctl status inify --no-pager

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
