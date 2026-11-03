# -*- coding: utf-8 -*-
"""ARC-02/03 + SEC-05e: durable outbox with retry/DLQ/crash recovery, and SSRF protection."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.agents.models import OutboxEvent, Webhook
from apps.agents.webhook_service import dispatch_webhook
from services import outbox
from services.url_safety import UnsafeURLError, validate_outbound_url
from tests.helpers import make_agent

CALLS = []


@outbox.register('test.ok')
def _ok(payload, event):
    CALLS.append(payload['n'])


@outbox.register('test.fail')
def _fail(payload, event):
    raise RuntimeError('boom')


@override_settings(OUTBOX_INLINE_DISPATCH=False)
class OutboxTests(TestCase):
    def setUp(self):
        CALLS.clear()

    def test_success_and_dedup(self):
        e1 = outbox.enqueue('test.ok', {'n': 1}, dedup_key='k1')
        e2 = outbox.enqueue('test.ok', {'n': 1}, dedup_key='k1')
        self.assertEqual(e1.id, e2.id)
        self.assertEqual(outbox.process_due(), 1)
        self.assertEqual(CALLS, [1])
        self.assertEqual(OutboxEvent.objects.get(id=e1.id).status, 'completed')
        self.assertEqual(outbox.process_due(), 0)  # never re-run

    def test_retry_then_dead_letter_then_requeue(self):
        ev = outbox.enqueue('test.fail', {}, max_attempts=2)
        outbox.process_due()
        ev.refresh_from_db()
        self.assertEqual((ev.status, ev.attempts), ('pending', 1))
        self.assertGreater(ev.next_attempt_at, timezone.now())
        OutboxEvent.objects.filter(id=ev.id).update(next_attempt_at=timezone.now())
        outbox.process_due()
        ev.refresh_from_db()
        self.assertEqual(ev.status, 'dead')
        self.assertEqual(outbox.requeue(), 1)
        ev.refresh_from_db()
        self.assertEqual((ev.status, ev.attempts), ('pending', 0))

    def test_crashed_worker_job_is_recovered(self):
        ev = outbox.enqueue('test.ok', {'n': 7})
        OutboxEvent.objects.filter(id=ev.id).update(
            status='processing', locked_until=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(outbox.process_due(), 1)
        self.assertEqual(CALLS, [7])

    def test_locked_job_not_double_processed(self):
        ev = outbox.enqueue('test.ok', {'n': 9})
        OutboxEvent.objects.filter(id=ev.id).update(
            status='processing', locked_until=timezone.now() + timedelta(minutes=5)
        )
        self.assertEqual(outbox.process_due(), 0)
        self.assertEqual(CALLS, [])


@override_settings(OUTBOX_INLINE_DISPATCH=False)
class WebhookDispatchTests(TestCase):
    def test_dispatch_creates_durable_jobs_per_subscribed_hook(self):
        agent = make_agent('hook_owner')
        Webhook.objects.create(agent=agent, name='a', url='https://example.com/a', events=['lead.created'], secret='s')
        Webhook.objects.create(agent=agent, name='b', url='https://example.com/b', events=['viewing.booked'], secret='s')
        dispatch_webhook(agent, 'lead.created', {'id': 'x'})
        jobs = OutboxEvent.objects.filter(topic='webhook.deliver')
        self.assertEqual(jobs.count(), 1)
        self.assertEqual(jobs.first().payload['event'], 'lead.created')

    @patch('apps.agents.webhook_service._send_single', return_value=False)
    def test_failed_delivery_is_retried(self, _):
        agent = make_agent('hook_owner2')
        Webhook.objects.create(agent=agent, name='a', url='https://example.com/a', events=['lead.created'], secret='s')
        dispatch_webhook(agent, 'lead.created', {'id': 'x'})
        outbox.process_due()
        job = OutboxEvent.objects.get(topic='webhook.deliver')
        self.assertEqual((job.status, job.attempts), ('pending', 1))


class SSRFTests(TestCase):
    def _blocked(self, url):
        with self.assertRaises(UnsafeURLError):
            validate_outbound_url(url)

    @override_settings(OUTBOUND_WEBHOOK_ALLOW_HTTP=False)
    def test_blocked_targets(self):
        for url in ['http://example.com', 'https://127.0.0.1/x', 'https://localhost/x', 'https://10.0.0.5/',
                    'https://192.168.1.1/', 'https://169.254.169.254/latest/meta-data', 'https://[::1]/',
                    'https://user:pass@example.com/', 'ftp://example.com', 'https://0.0.0.0/', 'https://100.64.0.1/']:
            with self.subTest(url=url):
                self._blocked(url)

    @patch('services.url_safety.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 443))])
    def test_public_https_allowed(self, _):
        self.assertEqual(validate_outbound_url('https://example.com/hook'), 'https://example.com/hook')

    @patch('services.url_safety.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('10.1.2.3', 443))])
    def test_dns_resolving_to_private_blocked(self, _):
        self._blocked('https://rebind.example.com/hook')

    def test_webhook_api_rejects_internal_url(self):
        agent = make_agent('hook_api', subscription_plan='enterprise')
        self.client.force_login(agent.user)
        response = self.client.post('/api/v1/agents/webhooks/', data={
            'name': 'x', 'url': 'https://127.0.0.1/hook', 'events': ['lead.created']
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)
