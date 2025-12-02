-- ═══════════════════════════════════════════════════════════
-- 🗄️ Inify - PostgreSQL Database Setup
-- ═══════════════════════════════════════════════════════════

-- Run this script as postgres superuser:
-- sudo -u postgres psql -f setup_postgres.sql

-- 1. Create Database
CREATE DATABASE inify_production
    WITH 
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0;

-- 2. Create User
CREATE USER inify_user WITH PASSWORD 'InifyDB@2024!Secure';

-- 3. Grant Privileges
GRANT ALL PRIVILEGES ON DATABASE inify_production TO inify_user;

-- 4. Connect to the database
\c inify_production

-- 5. Grant schema privileges
GRANT ALL ON SCHEMA public TO inify_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO inify_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO inify_user;

-- 6. Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO inify_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO inify_user;

-- ═══════════════════════════════════════════════════════════
-- ✅ Database setup complete!
-- ═══════════════════════════════════════════════════════════
