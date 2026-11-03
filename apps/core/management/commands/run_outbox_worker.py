# -*- coding: utf-8 -*-
"""
Independent worker for the durable Outbox (outbound webhooks, notifications, ...).

Usage:
    python manage.py run_outbox_worker                    # loop forever
    python manage.py run_outbox_worker --once             # one pass (cron)
    python manage.py run_outbox_worker --queues integrations,notifications

Run it as its own process/service (e.g. a Render "Background Worker"), never inside the web process.
Several workers may run concurrently: jobs are claimed atomically.
"""

import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from services import outbox

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process due Outbox jobs with retries and DLQ'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Single pass then exit')
        parser.add_argument('--interval', type=float, default=2.0, help='Seconds between polls')
        parser.add_argument('--batch', type=int, default=50)
        parser.add_argument('--queues', type=str, default='', help='Comma separated queue names')

    def handle(self, *args, **options):
        queues = [q.strip() for q in options['queues'].split(',') if q.strip()] or None
        self._stop = False

        def _graceful(*_):
            self._stop = True

        signal.signal(signal.SIGTERM, _graceful)
        signal.signal(signal.SIGINT, _graceful)

        while True:
            close_old_connections()
            try:
                done = outbox.process_due(limit=options['batch'], queues=queues)
            except Exception:
                logger.exception('Outbox worker pass failed')
                done = 0
            if options['once']:
                self.stdout.write(f'processed={done}')
                return
            if self._stop:
                return
            if not done:
                time.sleep(options['interval'])
