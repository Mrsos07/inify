# -*- coding: utf-8 -*-
"""SEC-05c: Partner API keys are header-only, stored hashed, scoped, and legacy keys keep working."""

from django.test import TestCase

from apps.agents.models import APIKey
from tests.helpers import make_agent, make_property

URL = '/api/v1/properties/ext/properties/'


class PartnerAPIKeyTests(TestCase):
    def setUp(self):
        self.agent = make_agent('api_owner', subscription_plan='enterprise')
        self.other = make_agent('api_other', subscription_plan='enterprise')
        make_property(self.agent, title='عقار المالك')
        make_property(self.other, title='عقار آخر')
        self.key_obj, self.raw = APIKey.create_for_agent(self.agent, 'main')

    def test_new_key_not_stored_in_plaintext(self):
        self.key_obj.refresh_from_db()
        self.assertIsNone(self.key_obj.key)
        self.assertEqual(self.key_obj.key_hash, APIKey.hash_key(self.raw))

    def test_header_auth_and_tenant_scoping(self):
        response = self.client.get(URL, HTTP_X_API_KEY=self.raw)
        self.assertEqual(response.status_code, 200)
        titles = [p['title'] for p in response.json()['properties']]
        self.assertEqual(titles, ['عقار المالك'])

    def test_query_string_key_rejected(self):
        response = self.client.get(URL + f'?api_key={self.raw}')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['code'], 'api_key_in_query')

    def test_invalid_key_rejected(self):
        self.assertEqual(self.client.get(URL, HTTP_X_API_KEY='nope').status_code, 401)

    def test_read_only_scope_cannot_write(self):
        _, raw = APIKey.create_for_agent(self.agent, 'ro', scopes=['properties:read'])
        response = self.client.post(URL, data='{}', content_type='application/json', HTTP_X_API_KEY=raw)
        self.assertEqual(response.status_code, 403)

    def test_legacy_plaintext_key_still_works_and_is_migrated(self):
        legacy_raw = APIKey.generate_key()
        legacy = APIKey.objects.create(agent=self.agent, name='legacy', key=legacy_raw)
        self.assertEqual(self.client.get(URL, HTTP_X_API_KEY=legacy_raw).status_code, 200)
        legacy.refresh_from_db()
        self.assertEqual(legacy.key_hash, APIKey.hash_key(legacy_raw))

    def test_idempotent_create(self):
        body = '{"title":"جديد","property_type":"apartment","status":"for_sale","city":"الرياض","price":1000,"size":100}'
        first = self.client.post(URL, data=body, content_type='application/json',
                                 HTTP_X_API_KEY=self.raw, HTTP_IDEMPOTENCY_KEY='abc')
        second = self.client.post(URL, data=body, content_type='application/json',
                                  HTTP_X_API_KEY=self.raw, HTTP_IDEMPOTENCY_KEY='abc')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()['property']['id'], second.json()['property']['id'])

    def test_bad_pagination_returns_400(self):
        response = self.client.get(URL + '?page=x', HTTP_X_API_KEY=self.raw)
        self.assertEqual(response.status_code, 400)
