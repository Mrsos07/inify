#!/usr/bin/env python
"""Check all URLs including allauth"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.urls import get_resolver

def show_urls(urllist, prefix=''):
    for entry in urllist:
        pattern = str(entry.pattern)
        full_path = prefix + pattern
        
        if hasattr(entry, 'url_patterns'):
            show_urls(entry.url_patterns, full_path)
        else:
            if 'google' in full_path or 'callback' in full_path:
                print(full_path)

print("=== Google OAuth URLs ===")
show_urls(get_resolver().url_patterns)
