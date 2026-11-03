# -*- coding: utf-8 -*-
"""SEC-02: server-side role enforcement for team members (viewer = read-only, inactive = no writes)."""

import json

from django.test import TestCase

from apps.agents.models import TeamMember
from tests.helpers import make_agent, make_property

WRITE_URL = '/api/v1/properties/save-json/'


class RolePermissionTests(TestCase):
    def setUp(self):
        self.owner = make_agent('org_owner', subscription_plan='enterprise')
        self.member = make_agent('org_member')
        self.membership = TeamMember.objects.create(owner_agent=self.owner, user=self.member.user, role='viewer')

    def _write(self, agent):
        self.client.force_login(agent.user)
        return self.client.post(WRITE_URL, data=json.dumps({'title': 'x'}), content_type='application/json')

    def test_viewer_cannot_write(self):
        response = self._write(self.member)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'role_forbidden')

    def test_viewer_can_read(self):
        make_property(self.member)
        self.client.force_login(self.member.user)
        self.assertEqual(self.client.get('/api/v1/properties/my/').status_code, 200)

    def test_viewer_can_manage_own_profile(self):
        self.client.force_login(self.member.user)
        response = self.client.post('/api/profile/update/', data='{}', content_type='application/json')
        self.assertNotEqual(response.status_code, 403)

    def test_marketer_can_write(self):
        self.membership.role = 'marketer'
        self.membership.save()
        self.assertNotEqual(self._write(self.member).status_code, 403)

    def test_inactive_member_cannot_write(self):
        self.membership.role = 'marketer'
        self.membership.is_active = False
        self.membership.save()
        self.assertEqual(self._write(self.member).status_code, 403)

    def test_owner_unaffected(self):
        self.assertNotEqual(self._write(self.owner).status_code, 403)
