# -*- coding: utf-8 -*-
"""
Create a local development `.env` from `.env.example` with freshly generated, dev-only keys.

Usage (from the project root):
    python scripts/create_dev_env.py

Never copies production values. Refuses to overwrite an existing `.env`.
"""

import secrets
import sys
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / '.env.example'
TARGET = ROOT / '.env'

GENERATED = {
    'DJANGO_SECRET_KEY': lambda: secrets.token_urlsafe(50),
    'ADMIN_SECRET_KEY': lambda: secrets.token_urlsafe(32),
    'FIELD_ENCRYPTION_KEY': lambda: Fernet.generate_key().decode(),
}
OVERRIDES = {
    'DEBUG': 'True',
    'ALLOWED_HOSTS': 'localhost,127.0.0.1',
    'ADMIN_USERNAME': '',
    'ADMIN_PASSWORD': '',
    'SITE_URL': 'http://127.0.0.1:8000',
    'RECAPTCHA_DISABLED': 'True',
}


def main():
    if TARGET.exists():
        print(f'{TARGET} already exists - not overwritten.')
        return 1
    lines = []
    for line in EXAMPLE.read_text(encoding='utf-8').splitlines():
        key = line.split('=', 1)[0].strip() if '=' in line and not line.lstrip().startswith('#') else None
        if key in GENERATED:
            line = f'{key}={GENERATED[key]()}'
        elif key in OVERRIDES:
            line = f'{key}={OVERRIDES[key]}'
        elif key and 'your' in line.split('=', 1)[1].lower():
            # Placeholders would be sent to real providers (OpenAI, Resend, ...) - leave them empty.
            line = f'{key}='
        lines.append(line)
    if 'RECAPTCHA_DISABLED' not in {l.split('=', 1)[0] for l in lines}:
        lines.append('RECAPTCHA_DISABLED=True')
    TARGET.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Created {TARGET} with dev-only generated keys.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
