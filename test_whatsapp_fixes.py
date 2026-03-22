# -*- coding: utf-8 -*-
"""
Tests for WhatsApp conflict protection and stuck instance cleanup.
Run: python manage.py test test_whatsapp_fixes --verbosity=2
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import json
from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth import get_user_model

from apps.agents.models import Agent, WhatsAppInstance

User = get_user_model()


class BaseWhatsAppTest(TestCase):
    """Base test class with shared setup"""

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='testuser', email='test@test.com', password='testpass123'
        )
        self.agent = Agent.objects.create(
            user=self.user,
            company_name='Test Company',
            subscription_plan='basic'
        )
        # Create active subscription so existing tests pass with subscription checks
        from apps.agents.models import Subscription
        Subscription.objects.create(
            agent=self.agent,
            plan_key='monthly',
            status='active',
            amount=199,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=29),
        )

    def _create_instance(self, name='test_instance_001', status='connected', **kwargs):
        return WhatsAppInstance.objects.create(
            agent=self.agent,
            instance_name=name,
            status=status,
            **kwargs
        )


class TestConflictDetection(BaseWhatsAppTest):
    """Test 1: Conflict/replaced detection stops reconnect"""

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_conflict_sets_disconnected_and_blocks(self, mock_ws):
        """conflict → status=disconnected + cache block"""
        from apps.core.whatsapp_views import whatsapp_webhook
        instance = self._create_instance(status='connected')

        body = {
            'event': 'CONNECTION_UPDATE',
            'instance': 'test_instance_001',
            'data': {
                'state': 'close',
                'reason': 'conflict'
            }
        }
        mock_ws.parse_webhook_message.return_value = {
            'event': 'connection',
            'instance': 'test_instance_001',
            'state': 'close',
            'raw': {'reason': 'conflict'}
        }

        import json
        request = self.factory.post(
            f'/webhooks/whatsapp/{instance.instance_name}/',
            data=json.dumps(body),
            content_type='application/json'
        )
        response = whatsapp_webhook(request, instance.instance_name)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'disconnected')
        self.assertTrue(cache.get(f'wa_conflict:{instance.instance_name}'))
        self.assertEqual(response.status_code, 200)
        print("  ✅ PASS: conflict → disconnected + cache block")

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_replaced_sets_disconnected(self, mock_ws):
        """replaced → status=disconnected"""
        from apps.core.whatsapp_views import whatsapp_webhook
        instance = self._create_instance(status='connected')

        mock_ws.parse_webhook_message.return_value = {
            'event': 'connection',
            'instance': 'test_instance_001',
            'state': 'close',
            'raw': {'lastDisconnect': {'error': {'output': {'payload': {'error': 'replaced'}}}}}
        }

        import json
        request = self.factory.post(
            f'/webhooks/whatsapp/{instance.instance_name}/',
            data=json.dumps({'event': 'CONNECTION_UPDATE', 'data': {'state': 'close'}}),
            content_type='application/json'
        )
        response = whatsapp_webhook(request, instance.instance_name)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'disconnected')
        print("  ✅ PASS: replaced → disconnected")

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_status_440_sets_disconnected(self, mock_ws):
        """statusReason=440 → disconnected"""
        from apps.core.whatsapp_views import whatsapp_webhook
        instance = self._create_instance(status='connected')

        mock_ws.parse_webhook_message.return_value = {
            'event': 'connection',
            'instance': 'test_instance_001',
            'state': 'close',
            'raw': {'statusReason': 440}
        }

        import json
        request = self.factory.post(
            f'/webhooks/whatsapp/{instance.instance_name}/',
            data=json.dumps({'event': 'CONNECTION_UPDATE', 'data': {'state': 'close'}}),
            content_type='application/json'
        )
        whatsapp_webhook(request, instance.instance_name)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'disconnected')
        print("  ✅ PASS: statusReason=440 → disconnected")


class TestReconnectRateLimit(BaseWhatsAppTest):
    """Test 2: Reconnect rate limiting (max 3 attempts / 5 min)"""

    @patch('apps.core.whatsapp_views._auto_reconnect_whatsapp')
    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_first_disconnect_triggers_reconnect(self, mock_ws, mock_reconnect):
        """Normal disconnect → reconnect attempt 1/3"""
        from apps.core.whatsapp_views import whatsapp_webhook
        instance = self._create_instance(status='connected')

        mock_ws.parse_webhook_message.return_value = {
            'event': 'connection',
            'instance': instance.instance_name,
            'state': 'close',
            'raw': {}
        }

        import json
        request = self.factory.post(
            f'/webhooks/whatsapp/{instance.instance_name}/',
            data=json.dumps({'event': 'CONNECTION_UPDATE'}),
            content_type='application/json'
        )
        whatsapp_webhook(request, instance.instance_name)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'connecting')
        self.assertEqual(cache.get(f'wa_reconnect_count:{instance.instance_name}'), 1)
        print("  ✅ PASS: normal disconnect → reconnect attempt 1/3")

    @patch('apps.core.whatsapp_views._auto_reconnect_whatsapp')
    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_fourth_disconnect_blocked(self, mock_ws, mock_reconnect):
        """4th disconnect in 5 min → blocked"""
        from apps.core.whatsapp_views import whatsapp_webhook
        instance = self._create_instance(status='connected')

        # Simulate 3 previous attempts
        cache.set(f'wa_reconnect_count:{instance.instance_name}', 3, 300)

        mock_ws.parse_webhook_message.return_value = {
            'event': 'connection',
            'instance': instance.instance_name,
            'state': 'close',
            'raw': {}
        }

        import json
        request = self.factory.post(
            f'/webhooks/whatsapp/{instance.instance_name}/',
            data=json.dumps({'event': 'CONNECTION_UPDATE'}),
            content_type='application/json'
        )
        whatsapp_webhook(request, instance.instance_name)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'disconnected')
        print("  ✅ PASS: 4th disconnect → blocked (rate limit)")

    @patch('apps.core.whatsapp_views._auto_reconnect_whatsapp')
    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_reconnect_blocked_after_conflict(self, mock_ws, mock_reconnect):
        """Normal disconnect after recent conflict → blocked"""
        from apps.core.whatsapp_views import whatsapp_webhook
        instance = self._create_instance(status='connected')

        # Simulate recent conflict
        cache.set(f'wa_conflict:{instance.instance_name}', True, 300)

        mock_ws.parse_webhook_message.return_value = {
            'event': 'connection',
            'instance': instance.instance_name,
            'state': 'close',
            'raw': {}
        }

        import json
        request = self.factory.post(
            f'/webhooks/whatsapp/{instance.instance_name}/',
            data=json.dumps({'event': 'CONNECTION_UPDATE'}),
            content_type='application/json'
        )
        whatsapp_webhook(request, instance.instance_name)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'disconnected')
        print("  ✅ PASS: reconnect blocked after recent conflict")


class TestSuccessfulConnectionClearsCounters(BaseWhatsAppTest):
    """Test 3: Successful connection clears all counters"""

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_open_clears_conflict_and_counter(self, mock_ws):
        """state=open → clears conflict flag + reconnect counter"""
        from apps.core.whatsapp_views import whatsapp_webhook
        instance = self._create_instance(status='connecting')

        # Set counters
        cache.set(f'wa_conflict:{instance.instance_name}', True, 300)
        cache.set(f'wa_reconnect_count:{instance.instance_name}', 2, 300)

        mock_ws.parse_webhook_message.return_value = {
            'event': 'connection',
            'instance': instance.instance_name,
            'state': 'open',
            'raw': {}
        }

        import json
        request = self.factory.post(
            f'/webhooks/whatsapp/{instance.instance_name}/',
            data=json.dumps({'event': 'CONNECTION_UPDATE'}),
            content_type='application/json'
        )
        whatsapp_webhook(request, instance.instance_name)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'connected')
        self.assertIsNone(cache.get(f'wa_conflict:{instance.instance_name}'))
        self.assertIsNone(cache.get(f'wa_reconnect_count:{instance.instance_name}'))
        print("  ✅ PASS: open → clears all counters")


class TestLogout401(BaseWhatsAppTest):
    """Test 4: statusReason=401 sets qr_ready (no reconnect)"""

    @patch('apps.core.whatsapp_views._auto_reconnect_whatsapp')
    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_401_sets_qr_ready(self, mock_ws, mock_reconnect):
        """statusReason=401 → qr_ready, no reconnect"""
        from apps.core.whatsapp_views import whatsapp_webhook
        instance = self._create_instance(status='connected')

        mock_ws.parse_webhook_message.return_value = {
            'event': 'connection',
            'instance': instance.instance_name,
            'state': 'close',
            'raw': {'statusReason': 401}
        }

        import json
        request = self.factory.post(
            f'/webhooks/whatsapp/{instance.instance_name}/',
            data=json.dumps({'event': 'CONNECTION_UPDATE'}),
            content_type='application/json'
        )
        whatsapp_webhook(request, instance.instance_name)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'qr_ready')
        mock_reconnect.assert_not_called()
        print("  ✅ PASS: 401 → qr_ready, no reconnect triggered")


class TestStuckInstanceCleanup(BaseWhatsAppTest):
    """Test 5: Auto-cleanup of stuck connecting instances"""

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_stuck_instance_deleted(self, mock_ws):
        """Instance stuck > 30 min → deleted from DB and Evolution API"""
        from apps.core.whatsapp_views import _cleanup_stuck_instances

        instance = self._create_instance(name='stuck_inst_001', status='connecting')
        # Simulate being stuck for 35 minutes
        WhatsAppInstance.objects.filter(pk=instance.pk).update(
            updated_at=timezone.now() - timedelta(minutes=35)
        )

        mock_ws.get_instance_status.return_value = {'success': False}
        mock_ws.delete_instance.return_value = {'success': True}

        count = _cleanup_stuck_instances()

        self.assertEqual(count, 1)
        self.assertFalse(WhatsAppInstance.objects.filter(pk=instance.pk).exists())
        mock_ws.delete_instance.assert_called_once_with('stuck_inst_001')
        print("  ✅ PASS: stuck instance (35min) → deleted")

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_recent_instance_not_deleted(self, mock_ws):
        """Instance connecting for < 30 min → NOT deleted"""
        from apps.core.whatsapp_views import _cleanup_stuck_instances

        instance = self._create_instance(name='new_inst_001', status='connecting')
        # 10 minutes ago — should NOT be cleaned
        WhatsAppInstance.objects.filter(pk=instance.pk).update(
            updated_at=timezone.now() - timedelta(minutes=10)
        )

        count = _cleanup_stuck_instances()

        self.assertEqual(count, 0)
        self.assertTrue(WhatsAppInstance.objects.filter(pk=instance.pk).exists())
        print("  ✅ PASS: recent instance (10min) → NOT deleted")

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_actually_connected_not_deleted(self, mock_ws):
        """Instance stuck in DB but actually connected in Evolution → updated, not deleted"""
        from apps.core.whatsapp_views import _cleanup_stuck_instances

        instance = self._create_instance(name='alive_inst_001', status='connecting')
        WhatsAppInstance.objects.filter(pk=instance.pk).update(
            updated_at=timezone.now() - timedelta(minutes=35)
        )

        # Evolution API says it's actually connected
        mock_ws.get_instance_status.return_value = {
            'success': True,
            'data': {'instance': {'state': 'open'}}
        }

        count = _cleanup_stuck_instances()

        self.assertEqual(count, 0)
        instance.refresh_from_db()
        self.assertEqual(instance.status, 'connected')
        mock_ws.delete_instance.assert_not_called()
        print("  ✅ PASS: actually connected → updated status, NOT deleted")

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_connected_instance_never_touched(self, mock_ws):
        """Already connected instance → never affected by cleanup"""
        from apps.core.whatsapp_views import _cleanup_stuck_instances

        instance = self._create_instance(name='ok_inst_001', status='connected')
        WhatsAppInstance.objects.filter(pk=instance.pk).update(
            updated_at=timezone.now() - timedelta(minutes=60)
        )

        count = _cleanup_stuck_instances()

        self.assertEqual(count, 0)
        instance.refresh_from_db()
        self.assertEqual(instance.status, 'connected')
        print("  ✅ PASS: connected instance → never touched by cleanup")


class TestNormalFlowUnaffected(BaseWhatsAppTest):
    """Test 6: Normal operations are NOT affected by fixes"""

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_normal_message_still_works(self, mock_ws):
        """Incoming message → still processed normally"""
        from apps.core.whatsapp_views import whatsapp_webhook
        instance = self._create_instance(status='connected')

        mock_ws.parse_webhook_message.return_value = {
            'event': 'message',
            'instance': instance.instance_name,
            'phone': '966500000000',
            'sender_name': 'Test User',
            'text': 'Hello',
            'is_group': False,
            'message_id': 'msg123',
            'timestamp': '2025-01-01T00:00:00',
            'raw': {}
        }

        import json
        request = self.factory.post(
            f'/webhooks/whatsapp/{instance.instance_name}/',
            data=json.dumps({'event': 'MESSAGES_UPSERT'}),
            content_type='application/json'
        )

        # auto_reply off so _process_whatsapp_message isn't called
        instance.auto_reply = False
        instance.save()

        response = whatsapp_webhook(request, instance.instance_name)
        self.assertEqual(response.status_code, 200)

        instance.refresh_from_db()
        self.assertEqual(instance.messages_received, 1)
        self.assertEqual(instance.status, 'connected')
        print("  ✅ PASS: incoming message → processed normally")

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_qrcode_event_still_works(self, mock_ws):
        """QR code event → still updates instance"""
        from apps.core.whatsapp_views import whatsapp_webhook
        instance = self._create_instance(status='connecting')

        mock_ws.parse_webhook_message.return_value = {
            'event': 'qrcode',
            'instance': instance.instance_name,
            'qrcode': 'data:image/png;base64,TEST_QR_DATA',
            'raw': {}
        }

        import json
        request = self.factory.post(
            f'/webhooks/whatsapp/{instance.instance_name}/',
            data=json.dumps({'event': 'QRCODE_UPDATED'}),
            content_type='application/json'
        )
        response = whatsapp_webhook(request, instance.instance_name)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'qr_ready')
        self.assertEqual(instance.qr_code, 'data:image/png;base64,TEST_QR_DATA')
        print("  ✅ PASS: QR code event → works normally")

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_normal_open_connection(self, mock_ws):
        """Normal open connection → status=connected"""
        from apps.core.whatsapp_views import whatsapp_webhook
        instance = self._create_instance(status='connecting')

        mock_ws.parse_webhook_message.return_value = {
            'event': 'connection',
            'instance': instance.instance_name,
            'state': 'open',
            'raw': {}
        }

        import json
        request = self.factory.post(
            f'/webhooks/whatsapp/{instance.instance_name}/',
            data=json.dumps({'event': 'CONNECTION_UPDATE'}),
            content_type='application/json'
        )
        whatsapp_webhook(request, instance.instance_name)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'connected')
        self.assertIsNotNone(instance.connected_at)
        print("  ✅ PASS: normal open → connected")


class TestAutoReconnectConflictCheck(BaseWhatsAppTest):
    """Test 7: _auto_reconnect_whatsapp respects conflict flag"""

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_reconnect_aborts_on_conflict(self, mock_ws):
        """Reconnect thread checks conflict before trying"""
        from apps.core.whatsapp_views import _auto_reconnect_whatsapp

        instance = self._create_instance(status='connecting')
        cache.set(f'wa_conflict:{instance.instance_name}', True, 300)

        with patch('time.sleep', return_value=None):
            _auto_reconnect_whatsapp(instance.instance_name)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'disconnected')
        mock_ws.restart_instance.assert_not_called()
        print("  ✅ PASS: reconnect aborts when conflict flag set")

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_reconnect_succeeds_when_already_open(self, mock_ws):
        """Reconnect finds instance already open → sets connected"""
        from apps.core.whatsapp_views import _auto_reconnect_whatsapp

        instance = self._create_instance(status='connecting')

        mock_ws.get_instance_status.return_value = {
            'success': True,
            'data': {'instance': {'state': 'open'}}
        }

        with patch('time.sleep', return_value=None):
            _auto_reconnect_whatsapp(instance.instance_name)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'connected')
        mock_ws.restart_instance.assert_not_called()
        print("  ✅ PASS: reconnect finds already open → connected")


class TestSubscriptionWhatsAppIntegration(BaseWhatsAppTest):
    """Test 8: Subscription/trial expiry disconnects WhatsApp"""

    def setUp(self):
        super().setUp()
        # Clear the default active subscription from BaseWhatsAppTest
        from apps.agents.models import Subscription
        Subscription.objects.filter(agent=self.agent).delete()

    def _create_subscription(self, status='trial', trial_days_left=5, active_days_left=30):
        from apps.agents.models import Subscription
        now = timezone.now()
        if status == 'trial':
            return Subscription.objects.create(
                agent=self.agent,
                plan_key='monthly',
                status='trial',
                amount=0,
                trial_start=now - timedelta(days=1),
                trial_end=now + timedelta(days=trial_days_left),
            )
        elif status == 'active':
            return Subscription.objects.create(
                agent=self.agent,
                plan_key='monthly',
                status='active',
                amount=199,
                start_date=now - timedelta(days=1),
                end_date=now + timedelta(days=active_days_left),
            )
        else:
            return Subscription.objects.create(
                agent=self.agent,
                plan_key='monthly',
                status=status,
                amount=0,
                trial_start=now - timedelta(days=10),
                trial_end=now - timedelta(days=5),
            )

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_status_check_disconnects_expired_trial(self, mock_ws):
        """whatsapp_status: expired trial → auto-disconnect"""
        from apps.core.whatsapp_views import whatsapp_status
        instance = self._create_instance(status='connected')
        self._create_subscription(status='trial', trial_days_left=-1)  # expired

        mock_ws.is_available = True

        request = self.factory.get('/api/whatsapp/status/')
        request.user = self.user

        response = whatsapp_status(request)
        data = json.loads(response.content)

        self.assertFalse(data['connected'])
        self.assertEqual(data['status'], 'disconnected')
        self.assertTrue(data.get('subscription_expired'))
        instance.refresh_from_db()
        self.assertEqual(instance.status, 'disconnected')
        print("  ✅ PASS: expired trial → auto-disconnect on status check")

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_status_check_keeps_active_trial(self, mock_ws):
        """whatsapp_status: active trial → stays connected"""
        from apps.core.whatsapp_views import whatsapp_status
        instance = self._create_instance(status='connected')
        self._create_subscription(status='trial', trial_days_left=3)  # still active

        mock_ws.is_available = True
        mock_ws.get_instance_status.return_value = {
            'success': True,
            'data': {'instance': {'state': 'open'}}
        }
        mock_ws.get_qr_code.return_value = {'success': False}

        request = self.factory.get('/api/whatsapp/status/')
        request.user = self.user

        response = whatsapp_status(request)
        data = json.loads(response.content)

        self.assertTrue(data['connected'])
        self.assertEqual(data['status'], 'connected')
        mock_ws.disconnect_instance.assert_not_called()
        print("  ✅ PASS: active trial → stays connected")

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_message_blocked_expired_subscription(self, mock_ws):
        """webhook message: expired subscription → no auto-reply + disconnect"""
        from apps.core.whatsapp_views import whatsapp_webhook
        instance = self._create_instance(status='connected')
        self._create_subscription(status='expired')

        mock_ws.parse_webhook_message.return_value = {
            'event': 'message',
            'instance': instance.instance_name,
            'phone': '966500000000',
            'sender_name': 'Test',
            'text': 'Hello',
            'is_group': False,
            'message_id': 'msg456',
            'timestamp': '2025-01-01T00:00:00',
            'raw': {}
        }

        request = self.factory.post(
            f'/webhooks/whatsapp/{instance.instance_name}/',
            data=json.dumps({'event': 'MESSAGES_UPSERT'}),
            content_type='application/json'
        )
        response = whatsapp_webhook(request, instance.instance_name)
        data = json.loads(response.content)

        self.assertEqual(data['status'], 'subscription_expired')
        instance.refresh_from_db()
        self.assertEqual(instance.status, 'disconnected')
        print("  ✅ PASS: expired subscription → message blocked + disconnect")

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_message_allowed_active_subscription(self, mock_ws):
        """webhook message: active subscription → message processed normally"""
        from apps.core.whatsapp_views import whatsapp_webhook
        instance = self._create_instance(status='connected')
        instance.auto_reply = False  # disable to avoid _process_whatsapp_message
        instance.save()
        self._create_subscription(status='active', active_days_left=20)

        mock_ws.parse_webhook_message.return_value = {
            'event': 'message',
            'instance': instance.instance_name,
            'phone': '966500000000',
            'sender_name': 'Test',
            'text': 'Hello',
            'is_group': False,
            'message_id': 'msg789',
            'timestamp': '2025-01-01T00:00:00',
            'raw': {}
        }

        request = self.factory.post(
            f'/webhooks/whatsapp/{instance.instance_name}/',
            data=json.dumps({'event': 'MESSAGES_UPSERT'}),
            content_type='application/json'
        )
        response = whatsapp_webhook(request, instance.instance_name)
        data = json.loads(response.content)

        self.assertEqual(data['status'], 'ok')
        instance.refresh_from_db()
        self.assertEqual(instance.messages_received, 1)
        self.assertEqual(instance.status, 'connected')
        mock_ws.disconnect_instance.assert_not_called()
        print("  ✅ PASS: active subscription → message processed normally")

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_reconnect_blocked_expired_subscription(self, mock_ws):
        """_auto_reconnect: expired subscription → blocked"""
        from apps.core.whatsapp_views import _auto_reconnect_whatsapp
        instance = self._create_instance(status='connecting')
        self._create_subscription(status='expired')

        with patch('time.sleep', return_value=None):
            _auto_reconnect_whatsapp(instance.instance_name)

        instance.refresh_from_db()
        self.assertEqual(instance.status, 'disconnected')
        mock_ws.restart_instance.assert_not_called()
        print("  ✅ PASS: expired subscription → reconnect blocked")

    @patch('apps.core.whatsapp_views.whatsapp_service')
    def test_no_subscription_at_all_disconnects(self, mock_ws):
        """whatsapp_status: no subscription → auto-disconnect"""
        from apps.core.whatsapp_views import whatsapp_status
        instance = self._create_instance(status='connected')
        # No subscription created

        mock_ws.is_available = True

        request = self.factory.get('/api/whatsapp/status/')
        request.user = self.user

        response = whatsapp_status(request)
        data = json.loads(response.content)

        self.assertFalse(data['connected'])
        self.assertTrue(data.get('subscription_expired'))
        instance.refresh_from_db()
        self.assertEqual(instance.status, 'disconnected')
        print("  ✅ PASS: no subscription → auto-disconnect")
