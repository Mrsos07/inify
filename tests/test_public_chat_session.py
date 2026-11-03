# -*- coding: utf-8 -*-
"""F-03: public chat conversations can only be continued with a valid signed session token."""

import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.chat.models import Conversation, Message
from tests.helpers import make_agent

URL = '/api/v1/chat/public/'


@patch('apps.chat.views.NewraAIService')
class PublicChatSessionTests(TestCase):
    def setUp(self):
        self.agent_a = make_agent('agent_a')
        self.agent_b = make_agent('agent_b')

    def _post(self, payload):
        return self.client.post(URL, data=json.dumps(payload), content_type='application/json')

    def _start(self, ai_mock, agent):
        ai_mock.return_value.chat.return_value = {'content': 'أهلاً'}
        response = self._post({'agent_id': str(agent.id), 'message': 'مرحبا'})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_new_conversation_returns_token(self, ai_mock):
        data = self._start(ai_mock, self.agent_a)
        self.assertTrue(data['session_token'])
        conv = Conversation.objects.get(id=data['conversation_id'])
        self.assertEqual(conv.agent_id, self.agent_a.id)

    def test_valid_token_continues_same_conversation(self, ai_mock):
        first = self._start(ai_mock, self.agent_a)
        second = self._post({
            'agent_id': str(self.agent_a.id), 'message': 'ثانية',
            'session_token': first['session_token'],
        }).json()
        self.assertEqual(second['conversation_id'], first['conversation_id'])
        self.assertEqual(Message.objects.filter(conversation_id=first['conversation_id']).count(), 4)

    def test_conversation_id_alone_does_not_grant_access(self, ai_mock):
        victim = self._start(ai_mock, self.agent_a)
        attacker = self._post({
            'agent_id': str(self.agent_a.id), 'message': 'اختراق',
            'conversation_id': victim['conversation_id'],
        }).json()
        self.assertNotEqual(attacker['conversation_id'], victim['conversation_id'])
        self.assertEqual(Message.objects.filter(conversation_id=victim['conversation_id']).count(), 2)

    def test_token_cannot_cross_agents(self, ai_mock):
        victim = self._start(ai_mock, self.agent_a)
        attacker = self._post({
            'agent_id': str(self.agent_b.id), 'message': 'اختراق',
            'session_token': victim['session_token'],
        }).json()
        self.assertNotEqual(attacker['conversation_id'], victim['conversation_id'])
        self.assertEqual(Conversation.objects.get(id=attacker['conversation_id']).agent_id, self.agent_b.id)
        self.assertEqual(Message.objects.filter(conversation_id=victim['conversation_id']).count(), 2)

    def test_tampered_token_starts_new_conversation(self, ai_mock):
        victim = self._start(ai_mock, self.agent_a)
        attacker = self._post({
            'agent_id': str(self.agent_a.id), 'message': 'اختراق',
            'session_token': victim['session_token'][:-2] + 'xx',
        }).json()
        self.assertNotEqual(attacker['conversation_id'], victim['conversation_id'])

    def test_expired_token_starts_new_conversation(self, ai_mock):
        first = self._start(ai_mock, self.agent_a)
        with override_settings(PUBLIC_CHAT_TOKEN_MAX_AGE=-1):
            second = self._post({
                'agent_id': str(self.agent_a.id), 'message': 'ثانية',
                'session_token': first['session_token'],
            }).json()
        self.assertNotEqual(second['conversation_id'], first['conversation_id'])

    def test_invalid_agent_id_returns_404(self, ai_mock):
        response = self._post({'agent_id': 'not-a-uuid', 'message': 'مرحبا'})
        self.assertEqual(response.status_code, 404)
