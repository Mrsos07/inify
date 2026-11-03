# -*- coding: utf-8 -*-
"""F-02: property appointments must only be visible to the property owner."""

from datetime import date, time, timedelta

from django.test import TestCase

from apps.leads.models import Lead, ViewingAppointment
from tests.helpers import make_agent, make_property


class PropertyAppointmentsAccessTests(TestCase):
    def setUp(self):
        self.owner = make_agent('owner')
        self.other = make_agent('other')
        self.prop = make_property(self.owner)
        lead = Lead.objects.create(agent=self.owner, name='عميل سري', phone='0555000111', notes='')
        ViewingAppointment.objects.create(
            lead=lead, property=self.prop, agent=self.owner,
            scheduled_date=date.today() + timedelta(days=1), scheduled_time=time(10, 0),
            notes='ملاحظة خاصة',
        )
        self.url = f'/api/v1/properties/{self.prop.id}/appointments/'

    def test_anonymous_is_rejected_without_pii(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertNotIn('0555000111', response.content.decode())

    def test_other_tenant_gets_404(self):
        self.client.force_login(self.other.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('0555000111', response.content.decode())

    def test_owner_sees_appointments(self):
        self.client.force_login(self.owner.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['appointments'][0]['client_phone'], '0555000111')
