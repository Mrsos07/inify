# -*- coding: utf-8 -*-
"""
Inspect / re-queue Outbox jobs that reached the DLQ (status=dead).

Usage:
    python manage.py outbox_requeue --list
    python manage.py outbox_requeue --all
    python manage.py outbox_requeue --id <uuid> [--id <uuid> ...]
    python manage.py outbox_requeue --topic webhook.deliver
"""

from django.core.management.base import BaseCommand, CommandError

from apps.agents.models import OutboxEvent
from services import outbox


class Command(BaseCommand):
    help = 'List or re-queue dead Outbox jobs'

    def add_arguments(self, parser):
        parser.add_argument('--list', action='store_true')
        parser.add_argument('--all', action='store_true')
        parser.add_argument('--id', action='append', default=[])
        parser.add_argument('--topic', type=str, default='')

    def handle(self, *args, **options):
        if options['list']:
            for ev in OutboxEvent.objects.filter(status='dead').order_by('-created_at')[:200]:
                self.stdout.write(f'{ev.id} {ev.topic} attempts={ev.attempts} error={ev.last_error[:120]}')
            return
        if not (options['all'] or options['id'] or options['topic']):
            raise CommandError('Use --list, --all, --id or --topic')
        count = outbox.requeue(event_ids=options['id'] or None, topic=options['topic'] or None)
        self.stdout.write(self.style.SUCCESS(f'requeued={count}'))
