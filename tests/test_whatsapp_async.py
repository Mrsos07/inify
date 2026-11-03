# -*- coding: utf-8 -*-
"""ARC-02: the WhatsApp webhook stores the message durably and returns without waiting for the LLM."""

import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.agents.models import OutboxEvent, WhatsAppInstance
from apps.chat.whatsapp_views import WhatsAppConversationBusy
from services import outbox
from tests.helpers import make_agent

URL = '/webhooks/whatsapp/inst_async/tok-123/'


def _message(message_id='MSG1'):
    return json.dumps({
        'event': 'messages.upsert', 'instance': 'inst_async',
        'data': {'key': {'remoteJid': '966500000001@s.whatsapp.net', 'fromMe': False, 'id': message_id},
                 'pushName': 'عميل', 'message': {'conversation': 'أبحث عن شقة'}},
    })


@override_settings(OUTBOX_INLINE_DISPATCH=False, WHATSAPP_ASYNC_PROCESSING=True)
class WhatsAppAsyncTests(TestCase):
    def setUp(self):
        self.agent = make_agent('wa_async')
        self.instance = WhatsAppInstance.objects.create(
            agent=self.agent, instance_name='inst_async', webhook_token='tok-123', status='connected'
        )

    def _post(self, body):
        return self.client.post(URL, data=body, content_type='application/json')

    @patch('apps.chat.whatsapp_views.WhatsAppWebhookView.reply_to_message')
    def test_webhook_queues_without_calling_llm(self, reply):
        response = self._post(_message())
        self.assertEqual(response.json().get('status'), 'queued')
        reply.assert_not_called()
        job = OutboxEvent.objects.get(topic='whatsapp.inbound_message')
        self.assertEqual(job.queue, 'messaging')
        self.assertEqual(job.payload['message_text'], 'أبحث عن شقة')

    @patch('apps.chat.whatsapp_views.WhatsAppWebhookView.reply_to_message')
    def test_redelivered_message_is_not_processed_twice(self, reply):
        self._post(_message('DUP'))
        self.assertEqual(self._post(_message('DUP')).json().get('status'), 'duplicate_message')
        self.assertEqual(OutboxEvent.objects.filter(topic='whatsapp.inbound_message').count(), 1)

    @patch('apps.chat.whatsapp_views.WhatsAppWebhookView.reply_to_message', return_value={'status': 'processed'})
    def test_worker_processes_job(self, reply):
        self._post(_message())
        self.assertEqual(outbox.process_due(), 1)
        reply.assert_called_once()

    @patch('apps.chat.whatsapp_views.WhatsAppWebhookView.reply_to_message',
           side_effect=WhatsAppConversationBusy('busy'))
    def test_busy_conversation_is_retried_not_dropped(self, _):
        self._post(_message())
        outbox.process_due()
        job = OutboxEvent.objects.get(topic='whatsapp.inbound_message')
        self.assertEqual((job.status, job.attempts), ('pending', 1))
