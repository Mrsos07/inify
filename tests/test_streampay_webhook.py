# -*- coding: utf-8 -*-
"""SEC-04 / DOM-03: StreamPay webhook integrity, replay protection, idempotency and server-side verification."""

import hashlib
import hmac
import json
import time
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.agents.models import Subscription
from services.streampay_service import streampay_service
from tests.helpers import make_agent

URL = '/webhooks/streampay/'
SECRET = 'test-webhook-secret-123'


def _signed(body, secret=SECRET, ts=None):
    ts = str(int(ts if ts is not None else time.time()))
    sig = hmac.new(secret.encode(), f'{ts}.{body}'.encode(), hashlib.sha256).hexdigest()
    return f't={ts},v1={sig}'


@patch.object(streampay_service, 'webhook_secret', SECRET)
class StreamPayWebhookTests(TestCase):
    def setUp(self):
        self.agent = make_agent('payer', active_subscription=False)
        self.sub = Subscription.objects.create(agent=self.agent, status='pending', plan_key='monthly')

    def _event(self, event_type='PAYMENT_SUCCEEDED', entity_id='pay-1', plan_key='monthly', **data):
        payload = {
            'event_type': event_type, 'entity_type': 'PAYMENT', 'entity_id': entity_id, 'status': 'SUCCEEDED',
            'data': {'payment': {'id': entity_id}, 'invoice': {'id': 'inv-1'},
                     'metadata': {'agent_id': str(self.agent.id), 'plan_key': plan_key}, **data},
        }
        return json.dumps(payload)

    def _post(self, body, signature=None):
        return self.client.post(URL, data=body, content_type='application/json',
                                HTTP_X_WEBHOOK_SIGNATURE=signature if signature is not None else _signed(body))

    @patch.object(streampay_service, 'get_payment', return_value={'status': 'SUCCEEDED', 'amount': '199.00', 'currency': 'SAR'})
    def test_valid_payment_activates_once(self, _):
        body = self._event()
        self.assertEqual(self._post(body).status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, 'active')
        first_end = self.sub.end_date
        # replay of the same event (even freshly re-signed) has no second effect
        response = self._post(body)
        self.assertEqual(response.json().get('status'), 'duplicate')
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.end_date, first_end)

    def test_missing_signature_rejected(self):
        self.assertEqual(self._post(self._event(), signature='').status_code, 401)

    def test_forged_signature_rejected(self):
        body = self._event()
        self.assertEqual(self._post(body, signature=_signed(body, secret='wrong')).status_code, 401)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, 'pending')

    def test_stale_signature_rejected(self):
        body = self._event()
        old = time.time() - 3 * 24 * 3600
        self.assertEqual(self._post(body, signature=_signed(body, ts=old)).status_code, 401)

    def test_unconfigured_secret_fails_closed(self):
        with patch.object(streampay_service, 'webhook_secret', ''):
            self.assertEqual(self._post(self._event(), signature='t=1,v1=x').status_code, 503)

    @patch.object(streampay_service, 'get_payment', return_value={'status': 'SUCCEEDED', 'amount': '10.00', 'currency': 'SAR'})
    def test_underpayment_rejected(self, _):
        response = self._post(self._event())
        self.assertEqual(response.json().get('reason'), 'amount_mismatch')
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, 'pending')

    @patch.object(streampay_service, 'get_payment', return_value={'status': 'SUCCEEDED', 'amount': '199.00', 'currency': 'USD'})
    def test_wrong_currency_rejected(self, _):
        self.assertEqual(self._post(self._event()).json().get('reason'), 'currency_mismatch')

    @patch.object(streampay_service, 'get_payment', return_value={'status': 'FAILED', 'amount': '199.00', 'currency': 'SAR'})
    def test_not_paid_at_provider_rejected(self, _):
        self.assertEqual(self._post(self._event()).json().get('reason'), 'status_FAILED')

    @patch.object(streampay_service, 'get_payment', return_value={'status': 'SUCCEEDED', 'amount': '199.00', 'currency': 'SAR'})
    def test_cheap_plan_payment_cannot_unlock_expensive_plan(self, _):
        self.assertEqual(self._post(self._event(plan_key='annual')).json().get('reason'), 'amount_mismatch')

    @patch.object(streampay_service, 'get_payment', return_value=None)
    def test_provider_unavailable_returns_503_and_retry_allowed(self, _):
        body = self._event()
        self.assertEqual(self._post(body).status_code, 503)
        with patch.object(streampay_service, 'get_payment',
                          return_value={'status': 'SUCCEEDED', 'amount': '199.00', 'currency': 'SAR'}):
            self.assertEqual(self._post(body).status_code, 200)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, 'active')

    def test_invoice_renewal_applied_once_and_not_for_initial_invoice(self):
        now = timezone.now()
        self.sub.status = 'active'
        self.sub.subscription_id = 'sp-sub-1'
        self.sub.invoice_id = 'inv-initial'
        self.sub.end_date = now + timedelta(days=30)
        self.sub.save()

        def invoice_event(invoice_id):
            return json.dumps({'event_type': 'INVOICE_COMPLETED', 'entity_type': 'INVOICE', 'entity_id': invoice_id,
                               'data': {'subscription_id': 'sp-sub-1'}})

        self._post(invoice_event('inv-initial'))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.end_date.date(), (now + timedelta(days=30)).date())

        self._post(invoice_event('inv-renew-1'))
        self._post(invoice_event('inv-renew-1'))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.end_date.date(), (now + timedelta(days=60)).date())


class PaymentRedirectTests(TestCase):
    def setUp(self):
        self.agent = make_agent('redirect_payer', active_subscription=False)
        self.sub = Subscription.objects.create(agent=self.agent, status='pending', plan_key='monthly')
        self.client.force_login(self.agent.user)

    @patch.object(streampay_service, 'get_invoice', return_value={'status': 'COMPLETED', 'amount': '199.00', 'currency': 'SAR'})
    def test_verified_invoice_activates(self, _):
        self.client.get('/payment/success/?status=paid&invoice_id=inv-9&payment_id=pay-9')
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, 'active')

    @patch.object(streampay_service, 'get_invoice', return_value={'status': 'COMPLETED', 'amount': '199.00', 'currency': 'SAR'})
    def test_invoice_cannot_be_reused_by_another_account(self, _):
        self.client.get('/payment/success/?status=paid&invoice_id=inv-9&payment_id=pay-9')
        other = make_agent('freeloader', active_subscription=False)
        other_sub = Subscription.objects.create(agent=other, status='pending', plan_key='monthly')
        self.client.force_login(other.user)
        self.client.get('/payment/success/?status=paid&invoice_id=inv-9&payment_id=pay-9')
        other_sub.refresh_from_db()
        self.assertEqual(other_sub.status, 'pending')

    @patch.object(streampay_service, 'get_invoice', return_value={'status': 'COMPLETED'})
    def test_unverifiable_amount_does_not_activate(self, _):
        response = self.client.get('/payment/success/?status=paid&invoice_id=inv-9')
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, 'pending')
        self.assertTrue(response.context['pending_confirmation'])
