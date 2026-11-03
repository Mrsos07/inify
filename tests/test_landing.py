# -*- coding: utf-8 -*-
"""The site root serves the real-estate product page; the old /estate/ URL redirects permanently."""

from django.test import TestCase


class LandingPageTests(TestCase):
    def test_root_serves_real_estate_product(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')
        self.assertTemplateNotUsed(response, 'company_home.html')

    def test_old_estate_url_redirects_permanently(self):
        response = self.client.get('/estate/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/')
