# -*- coding: utf-8 -*-
"""F-05: Evolution webhooks require the per-instance secret token; duplicates are deduplicated in DB."""

import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.agents.models import InboundWebhookEvent, WhatsAppInstance
from services.whatsapp_service import register_secure_webhook
from tests.helpers import make_agent

CONNECTION_EVENT = {'event': 'connection.update', 'instance': 'inst_a', 'data': {'state': 'open'}}


class WhatsAppWebhookAuthTests(TestCase):
    def setUp(self):
        self.agent = make_agent('wa_owner')
        self.instance = WhatsAppInstance.objects.create(
            agent=self.agent, instance_name='inst_a', webhook_token='s3cret-token-value', status='connecting'
        )

    def _post(self, path, body=CONNECTION_EVENT):
        return self.client.post(path, data=json.dumps(body), content_type='application/json')

    def test_missing_token_rejected_when_instance_has_token(self):
        self.assertEqual(self._post('/webhooks/whatsapp/inst_a/').status_code, 401)
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.status, 'connecting')

    def test_wrong_token_rejected(self):
        self.assertEqual(self._post('/webhooks/whatsapp/inst_a/wrong/').status_code, 401)

    def test_global_route_cannot_bypass_token(self):
        self.assertEqual(self._post('/webhooks/whatsapp/').status_code, 401)

    def test_unknown_instance_indistinguishable(self):
        self.assertEqual(self._post('/webhooks/whatsapp/nope/x/').status_code, 401)

    def test_valid_token_processed(self):
        response = self._post('/webhooks/whatsapp/inst_a/s3cret-token-value/')
        self.assertEqual(response.status_code, 200)
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.status, 'connected')

    def test_invalid_json_rejected(self):
        response = self.client.post('/webhooks/whatsapp/inst_a/s3cret-token-value/', data='{bad',
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)


class LegacyInstanceTests(TestCase):
    def setUp(self):
        self.agent = make_agent('wa_legacy')
        WhatsAppInstance.objects.create(agent=self.agent, instance_name='inst_a', status='connecting')

    def test_legacy_url_allowed_during_transition(self):
        response = self.client.post('/webhooks/whatsapp/inst_a/', data=json.dumps(CONNECTION_EVENT),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)

    @override_settings(WHATSAPP_WEBHOOK_LEGACY_ALLOWED=False)
    def test_legacy_url_rejected_after_transition(self):
        response = self.client.post('/webhooks/whatsapp/inst_a/', data=json.dumps(CONNECTION_EVENT),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 401)


class RegisterSecureWebhookTests(TestCase):
    def setUp(self):
        self.agent = make_agent('wa_reg')
        self.instance = WhatsAppInstance.objects.create(agent=self.agent, instance_name='inst_r')

    @patch('services.whatsapp_service.whatsapp_service.set_webhook', return_value={'success': True})
    def test_token_saved_only_after_success(self, set_webhook):
        register_secure_webhook(self.instance)
        self.instance.refresh_from_db()
        self.assertTrue(self.instance.webhook_token)
        url = set_webhook.call_args[0][1]
        self.assertTrue(url.endswith(f'/webhooks/whatsapp/inst_r/{self.instance.webhook_token}/'))

    @patch('services.whatsapp_service.whatsapp_service.set_webhook', return_value={'success': False})
    def test_token_not_saved_on_failure(self, _):
        register_secure_webhook(self.instance)
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.webhook_token, '')


class InboxDedupTests(TestCase):
    def test_record_once(self):
        self.assertTrue(InboundWebhookEvent.record_once('evolution', 'inst:1'))
        self.assertFalse(InboundWebhookEvent.record_once('evolution', 'inst:1'))
        self.assertTrue(InboundWebhookEvent.record_once('streampay', 'inst:1'))
