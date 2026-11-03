# -*- coding: utf-8 -*-
"""F-09 admin auth, F-11 CSRF enforcement, F-14 n8n webhook secret, F-07/F-08 cross-tenant writes, audit log."""

import json
import time
from datetime import date, time as dtime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings

from apps.agents.models import AuditEvent
from apps.leads.models import Lead, ViewingAppointment
from services.admin_auth import totp_now, verify_totp
from tests.helpers import make_agent, make_property

ADMIN_USERS_URL = '/api/admin/users/'
LOGIN_URL = '/api/admin/login/'
TOTP_SECRET = 'JBSWY3DPEHPK3PXP'


def _login(client, username, password, otp=''):
    return client.post(LOGIN_URL, data=json.dumps({'username': username, 'password': password,
                                                   'recaptcha_token': 'x', 'otp': otp}),
                       content_type='application/json')


@patch('apps.core.views.verify_recaptcha', return_value=True)
@override_settings(ADMIN_USERNAME='envadmin', ADMIN_PASSWORD='Env-Pass-123!', ADMIN_TOTP_SECRET='')
class AdminAuthTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # login lockout counters live in the cache

    def test_static_header_key_no_longer_grants_access(self, _):
        from django.conf import settings
        response = self.client.get(ADMIN_USERS_URL, HTTP_X_ADMIN_KEY=settings.ADMIN_SECRET_KEY)
        self.assertEqual(response.status_code, 403)

    def test_regular_tenant_user_is_not_admin(self, _):
        agent = make_agent('plain')
        self.client.force_login(agent.user)
        self.assertEqual(self.client.get(ADMIN_USERS_URL).status_code, 403)

    def test_superuser_identity_is_admin(self, _):
        su = get_user_model().objects.create_superuser('root', 'root@example.com', 'Root-Pass-123!')
        self.client.force_login(su)
        self.assertEqual(self.client.get(ADMIN_USERS_URL).status_code, 200)

    def test_platform_admin_group_member_can_login_and_is_audited(self, _):
        user = get_user_model().objects.create_user('ops', 'ops@example.com', 'Ops-Pass-123!')
        user.groups.add(Group.objects.create(name='platform_admin'))
        self.assertEqual(_login(self.client, 'ops', 'Ops-Pass-123!').status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(action='admin.login.success', actor='ops').exists())

    def test_env_credentials_still_work_and_wrong_password_fails(self, _):
        self.assertEqual(_login(self.client, 'envadmin', 'wrong').status_code, 401)
        self.assertTrue(AuditEvent.objects.filter(action='admin.login.failed').exists())
        self.assertEqual(_login(self.client, 'envadmin', 'Env-Pass-123!').status_code, 200)
        self.assertEqual(self.client.get(ADMIN_USERS_URL).status_code, 200)

    def test_spoofed_forwarded_for_does_not_bypass_lockout(self, _):
        for i in range(4):
            self.client.post(LOGIN_URL, data=json.dumps({'username': 'x', 'password': 'y', 'recaptcha_token': 'x'}),
                             content_type='application/json', HTTP_X_FORWARDED_FOR=f'10.0.0.{i}')
        response = self.client.post(LOGIN_URL, data=json.dumps({'username': 'envadmin', 'password': 'Env-Pass-123!',
                                                                 'recaptcha_token': 'x'}),
                                    content_type='application/json', HTTP_X_FORWARDED_FOR='10.9.9.9')
        self.assertEqual(response.status_code, 429)

    def test_admin_session_expires(self, _):
        _login(self.client, 'envadmin', 'Env-Pass-123!')
        session = self.client.session
        session['admin_authenticated_at'] = int(time.time()) - 9 * 3600
        session.save()
        self.assertEqual(self.client.get(ADMIN_USERS_URL).status_code, 403)

    def test_logout_ends_admin_session(self, _):
        _login(self.client, 'envadmin', 'Env-Pass-123!')
        self.client.post('/api/admin/logout/')
        self.assertEqual(self.client.get(ADMIN_USERS_URL).status_code, 403)

    def test_totp_required_when_configured(self, _):
        with override_settings(ADMIN_TOTP_SECRET=TOTP_SECRET):
            first = _login(self.client, 'envadmin', 'Env-Pass-123!')
            self.assertTrue(first.json().get('otp_required'))
            self.assertEqual(_login(self.client, 'envadmin', 'Env-Pass-123!', otp='000000').status_code, 401)
            self.assertEqual(_login(self.client, 'envadmin', 'Env-Pass-123!', otp=totp_now(TOTP_SECRET)).status_code, 200)


class TotpTests(TestCase):
    def test_rfc6238_reference_vector(self):
        # RFC 6238 SHA1 test secret "12345678901234567890" (base32) at T=59 → 94287082 (8 digits) → last 6 = 287082
        secret = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'  # public RFC 6238 test vector  # gitleaks:allow
        self.assertTrue(verify_totp(secret, '287082', window=0, at=59))
        self.assertFalse(verify_totp(secret, '287083', window=0, at=59))


class CsrfEnforcementTests(TestCase):
    def setUp(self):
        self.agent = make_agent('csrf_user')
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.agent.user)

    def test_session_write_without_token_rejected(self):
        response = self.client.post('/api/profile/update/', data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'csrf_failed')

    def test_session_write_with_token_accepted(self):
        self.client.get('/dashboard/')  # middleware issues the csrftoken cookie
        token = self.client.cookies['csrftoken'].value
        response = self.client.post('/api/profile/update/', data='{}', content_type='application/json',
                                    HTTP_X_CSRFTOKEN=token)
        self.assertNotEqual(response.status_code, 403)

    def test_drf_viewset_enforces_csrf(self):
        response = self.client.post('/api/v1/leads/', data={'name': 'x', 'phone': '1'},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_public_and_webhook_endpoints_remain_exempt(self):
        anon = Client(enforce_csrf_checks=True)
        self.assertNotEqual(anon.post('/webhooks/streampay/', data='{}', content_type='application/json').status_code, 403)
        self.assertNotEqual(anon.post('/api/v1/chat/public/', data='{}', content_type='application/json').status_code, 403)


class N8nWebhookTests(TestCase):
    def test_agent_without_secret_rejected(self):
        agent = make_agent('n8n_nosecret')
        response = self.client.post('/webhooks/chat/', data=json.dumps({'agent_id': str(agent.id), 'message': 'hi'}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_wrong_secret_rejected(self):
        agent = make_agent('n8n_secret', webhook_secret='right-secret')
        response = self.client.post('/webhooks/chat/', data=json.dumps({'agent_id': str(agent.id), 'message': 'hi'}),
                                    content_type='application/json', HTTP_X_WEBHOOK_SECRET='wrong')
        self.assertEqual(response.status_code, 403)

    def test_unknown_agent_indistinguishable(self):
        response = self.client.post('/webhooks/chat/', data=json.dumps({'agent_id': 'not-a-uuid', 'message': 'hi'}),
                                    content_type='application/json', HTTP_X_WEBHOOK_SECRET='x')
        self.assertEqual(response.status_code, 403)


class CrossTenantWriteTests(TestCase):
    def setUp(self):
        self.me = make_agent('me')
        self.victim = make_agent('victim')
        self.victim_prop = make_property(self.victim)
        self.victim_lead = Lead.objects.create(agent=self.victim, name='ضحية', phone='0500000999')
        self.my_prop = make_property(self.me)
        self.my_lead = Lead.objects.create(agent=self.me, name='عميلي', phone='0500000111')
        self.client.force_login(self.me.user)

    def _book(self, lead, prop):
        return self.client.post('/api/v1/leads/appointments/', data=json.dumps({
            'lead': str(lead.id), 'property': str(prop.id),
            'scheduled_date': str(date.today() + timedelta(days=2)), 'scheduled_time': '10:00',
        }), content_type='application/json')

    def test_cannot_book_with_foreign_lead_or_property(self):
        self.assertEqual(self._book(self.victim_lead, self.my_prop).status_code, 400)
        self.assertEqual(self._book(self.my_lead, self.victim_prop).status_code, 400)
        self.assertFalse(ViewingAppointment.objects.filter(lead=self.victim_lead).exists())

    def test_can_book_own_resources(self):
        self.assertEqual(self._book(self.my_lead, self.my_prop).status_code, 201)

    def test_cannot_create_calendar_for_foreign_property(self):
        response = self.client.post('/api/v1/leads/calendars/', data=json.dumps({'property': str(self.victim_prop.id)}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_public_lead_capture_ignores_foreign_property(self):
        self.client.logout()
        response = self.client.post(f'/api/v1/leads/chat/{self.me.id}/', data=json.dumps({
            'phone': '0555123000', 'name': 'زائر', 'interested_properties': [{'id': str(self.victim_prop.id)}],
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.victim_prop.refresh_from_db()
        self.assertEqual(self.victim_prop.interested_count, 0)

    def test_public_availability_hides_customer_names(self):
        ViewingAppointment.objects.create(lead=self.my_lead, property=self.my_prop, agent=self.me,
                                          scheduled_date=date.today() + timedelta(days=3), scheduled_time=dtime(11, 0))
        from apps.leads.models import PropertyCalendar
        PropertyCalendar.objects.get_or_create(property=self.my_prop)
        self.client.logout()
        response = self.client.get(f'/api/v1/leads/ai-agent/{self.me.id}/calendar/', {
            'property_id': str(self.my_prop.id), 'date': str(date.today() + timedelta(days=3)), 'time': '11:00',
        })
        self.assertNotIn('عميلي', response.content.decode())


class AuditLogTests(TestCase):
    def test_append_only(self):
        ev = AuditEvent.record('a', 'x.y')
        with self.assertRaises(PermissionError):
            ev.delete()
        ev.action = 'tampered'
        with self.assertRaises(PermissionError):
            ev.save()
