# -*- coding: utf-8 -*-
"""
Management command to setup Google OAuth for django-allauth.
"""

from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from django.conf import settings
from allauth.socialaccount.models import SocialApp


class Command(BaseCommand):
    help = 'Setup Google OAuth credentials for django-allauth'

    def add_arguments(self, parser):
        parser.add_argument(
            '--client-id',
            type=str,
            help='Google OAuth Client ID (defaults to GOOGLE_CLIENT_ID from settings)',
        )
        parser.add_argument(
            '--client-secret',
            type=str,
            help='Google OAuth Client Secret (defaults to GOOGLE_CLIENT_SECRET from settings)',
        )

    def handle(self, *args, **options):
        # Get credentials from arguments or settings
        client_id = options.get('client_id') or getattr(settings, 'GOOGLE_CLIENT_ID', '')
        client_secret = options.get('client_secret') or getattr(settings, 'GOOGLE_CLIENT_SECRET', '')

        if not client_id or not client_secret:
            self.stdout.write(self.style.ERROR(
                'Error: Google OAuth credentials not found!\n'
                'Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file\n'
                'Or provide them as arguments: --client-id=xxx --client-secret=xxx'
            ))
            return

        # Get or create the site
        site, created = Site.objects.get_or_create(
            id=settings.SITE_ID,
            defaults={
                'domain': 'inify.ai',
                'name': 'Inify AI'
            }
        )
        
        if not created:
            # Update site domain if needed
            site.domain = 'inify.ai'
            site.name = 'Inify AI'
            site.save()
            self.stdout.write(f'Updated site: {site.domain}')
        else:
            self.stdout.write(self.style.SUCCESS(f'Created site: {site.domain}'))

        # Create or update Google SocialApp
        social_app, created = SocialApp.objects.update_or_create(
            provider='google',
            defaults={
                'name': 'Google Login',
                'client_id': client_id,
                'secret': client_secret,
            }
        )

        # Add site to the social app
        if site not in social_app.sites.all():
            social_app.sites.add(site)

        if created:
            self.stdout.write(self.style.SUCCESS('✅ Google OAuth app created successfully!'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ Google OAuth app updated successfully!'))

        self.stdout.write(self.style.SUCCESS(
            '\n🎉 Google OAuth is now configured!\n\n'
            'Login URL: /accounts/google/login/\n'
            'Callback URL: /accounts/google/login/callback/\n\n'
            'Make sure to add this callback URL in Google Cloud Console:\n'
            'https://inify.ai/accounts/google/login/callback/'
        ))
