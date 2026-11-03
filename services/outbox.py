# -*- coding: utf-8 -*-
"""
Durable Outbox processing.

- `enqueue()` stores the job in PostgreSQL (same transaction as the business change when called inside one).
- `process_due()` is run by an independent worker: `python manage.py run_outbox_worker`.
- Jobs are claimed with an atomic conditional UPDATE, so several workers never run the same job concurrently.
- A crashed worker's job is re-claimed after its lock expires (no lost work).
- Failures are retried with exponential backoff + jitter, then moved to `dead` (DLQ).
  Re-queue manually with `python manage.py outbox_requeue`.

Delivery is at-least-once; handlers must be idempotent.
"""

import logging
import random
import threading
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

LOCK_SECONDS = 300
_HANDLERS = {}


def register(topic):
    """Decorator registering a handler `fn(payload: dict, event) -> None` for a topic."""
    def _wrap(fn):
        _HANDLERS[topic] = fn
        return fn
    return _wrap


def backoff_seconds(attempts):
    base = min(3600, 10 * (2 ** max(0, attempts - 1)))
    return base * random.uniform(0.8, 1.2)


def enqueue(topic, payload, agent=None, queue='integrations', dedup_key=None, max_attempts=6):
    """Persist a job. With `dedup_key`, enqueuing the same logical job twice is a no-op."""
    from apps.agents.models import OutboxEvent

    try:
        with transaction.atomic():
            event = OutboxEvent.objects.create(
                topic=topic, payload=payload, agent=agent, queue=queue,
                dedup_key=dedup_key, max_attempts=max_attempts,
            )
    except IntegrityError:
        return OutboxEvent.objects.get(dedup_key=dedup_key)

    if getattr(settings, 'OUTBOX_INLINE_DISPATCH', True):
        # Accelerator only: durability comes from the DB row; the worker retries anything that fails here.
        event_id = event.id
        transaction.on_commit(
            lambda: threading.Thread(target=_safe_process, args=(event_id,), daemon=True).start()
        )
    return event


def _safe_process(event_id):
    from django.db import close_old_connections
    try:
        process_event(event_id)
    except Exception:
        logger.exception('Outbox inline processing crashed for %s', event_id)
    finally:
        close_old_connections()


def _claim(event_id):
    from apps.agents.models import OutboxEvent
    from django.db.models import Q

    now = timezone.now()
    claimable = Q(status='pending', next_attempt_at__lte=now) | Q(status='processing', locked_until__lt=now)
    return OutboxEvent.objects.filter(Q(id=event_id) & claimable).update(
        status='processing', locked_until=now + timedelta(seconds=LOCK_SECONDS),
    ) == 1


def process_event(event_id):
    """Run one job if it is due and not claimed by another worker. Returns True on success."""
    from apps.agents.models import OutboxEvent

    if not _claim(event_id):
        return False
    event = OutboxEvent.objects.get(id=event_id)
    handler = _HANDLERS.get(event.topic)
    try:
        if handler is None:
            raise RuntimeError(f'No outbox handler registered for topic "{event.topic}"')
        handler(event.payload, event)
    except Exception as exc:
        attempts = event.attempts + 1
        dead = attempts >= event.max_attempts
        OutboxEvent.objects.filter(id=event.id).update(
            attempts=attempts,
            status='dead' if dead else 'pending',
            next_attempt_at=timezone.now() + timedelta(seconds=backoff_seconds(attempts)),
            locked_until=None,
            last_error=str(exc)[:2000],
        )
        log = logger.error if dead else logger.warning
        log('Outbox job %s (%s) failed attempt %s/%s: %s', event.id, event.topic, attempts, event.max_attempts, exc)
        return False

    OutboxEvent.objects.filter(id=event.id).update(
        attempts=event.attempts + 1, status='completed', completed_at=timezone.now(),
        locked_until=None, last_error='',
    )
    return True


def process_due(limit=50, queues=None):
    """Process due jobs (including ones abandoned by a crashed worker). Returns number processed."""
    from apps.agents.models import OutboxEvent
    from django.db.models import Q

    now = timezone.now()
    qs = OutboxEvent.objects.filter(
        Q(status='pending', next_attempt_at__lte=now) | Q(status='processing', locked_until__lt=now)
    )
    if queues:
        qs = qs.filter(queue__in=queues)
    done = 0
    for event_id in qs.order_by('next_attempt_at').values_list('id', flat=True)[:limit]:
        if process_event(event_id):
            done += 1
    return done


def requeue(event_ids=None, topic=None):
    """Move dead (DLQ) jobs back to pending."""
    from apps.agents.models import OutboxEvent

    qs = OutboxEvent.objects.filter(status='dead')
    if event_ids:
        qs = qs.filter(id__in=event_ids)
    if topic:
        qs = qs.filter(topic=topic)
    return qs.update(status='pending', attempts=0, next_attempt_at=timezone.now(), last_error='')
