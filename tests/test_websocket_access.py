# -*- coding: utf-8 -*-
"""F-04: the live WhatsApp WebSocket is restricted to the owner and scoped to the owner's data."""

import json
from unittest.mock import patch

from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from apps.chat.models import Conversation, Message
from apps.chat.routing import websocket_urlpatterns
from tests.helpers import make_agent

APP = URLRouter(websocket_urlpatterns)


class WebSocketAccessTests(TransactionTestCase):
    def setUp(self):
        self.owner = make_agent('ws_owner')
        self.other = make_agent('ws_other')
        self.other_conv = Conversation.objects.create(
            agent=self.other, source='whatsapp', client_phone='0555999888'
        )
        Message.objects.create(conversation=self.other_conv, role='user', content='رسالة سرية')

    async def _connect(self, user, agent):
        communicator = WebsocketCommunicator(APP, f'/ws/whatsapp/{agent.id}/')
        communicator.scope['user'] = user
        connected, _ = await communicator.connect()
        return communicator, connected

    async def test_anonymous_rejected(self):
        communicator, connected = await self._connect(AnonymousUser(), self.owner)
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_other_tenant_rejected(self):
        communicator, connected = await self._connect(self.other.user, self.owner)
        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_owner_connects_but_cannot_read_foreign_conversation(self):
        communicator, connected = await self._connect(self.owner.user, self.owner)
        self.assertTrue(connected)
        await communicator.receive_json_from()  # connection_established
        await communicator.send_to(text_data=json.dumps({
            'action': 'get_conversation', 'conversation_id': str(self.other_conv.id)
        }))
        reply = await communicator.receive_json_from()
        self.assertEqual(reply['type'], 'conversation_details')
        self.assertIsNone(reply['conversation'])
        await communicator.disconnect()

    @patch('services.whatsapp_service.whatsapp_service.send_text_message')
    async def test_owner_cannot_send_into_foreign_conversation(self, send_mock):
        communicator, connected = await self._connect(self.owner.user, self.owner)
        self.assertTrue(connected)
        await communicator.receive_json_from()
        await communicator.send_to(text_data=json.dumps({
            'action': 'send_message', 'conversation_id': str(self.other_conv.id), 'message': 'spam'
        }))
        reply = await communicator.receive_json_from()
        self.assertFalse(reply['result']['success'])
        send_mock.assert_not_called()
        await communicator.disconnect()
        count = await Message.objects.filter(conversation=self.other_conv).acount()
        self.assertEqual(count, 1)
