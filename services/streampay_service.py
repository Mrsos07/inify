# -*- coding: utf-8 -*-
"""
StreamPay Payment Service - خدمة الدفع عبر StreamPay
"""

import os
import base64
import hmac
import hashlib
import logging
import requests
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

STREAMPAY_BASE_URL = 'https://stream-app-service.streampay.sa/api/v2'


class StreamPayService:
    """خدمة التكامل مع StreamPay"""

    def __init__(self):
        self.api_key = os.environ.get('STREAMPAY_API_KEY', '')
        self.api_secret = os.environ.get('STREAMPAY_API_SECRET', '')
        self.webhook_secret = os.environ.get('STREAMPAY_WEBHOOK_SECRET', '')
        self.product_ids = {
            'trial_day': os.environ.get('STREAMPAY_PRODUCT_TRIAL_DAY_ID', ''),
            'monthly': os.environ.get('STREAMPAY_PRODUCT_MONTHLY_ID', ''),
            'quarterly': os.environ.get('STREAMPAY_PRODUCT_QUARTERLY_ID', ''),
            'semi': os.environ.get('STREAMPAY_PRODUCT_SEMI_ID', ''),
            'annual': os.environ.get('STREAMPAY_PRODUCT_ANNUAL_ID', ''),
        }

    def _get_auth_token(self):
        """Generate Base64-encoded auth token from api-key:api-secret"""
        credentials = f"{self.api_key}:{self.api_secret}"
        return base64.b64encode(credentials.encode()).decode()

    def _get_headers(self):
        """Get headers for API requests"""
        return {
            'x-api-key': self._get_auth_token(),
            'Content-Type': 'application/json',
        }

    def _get_site_url(self):
        """Get site URL for redirects"""
        return os.environ.get('SITE_URL', 'http://127.0.0.1:8000')

    # ─── Pricing Constants ───────────────────────────────────────────
    PLANS = {
        'trial_day': {
            'days': 1,
            'price': 1,
            'discount': 0,
            'label': 'يوم تجريبي',
        },
        'monthly': {
            'months': 1,
            'price': 199,
            'discount': 0,
            'label': 'شهري',
        },
        'quarterly': {
            'months': 3,
            'price': 537,
            'discount': 10,
            'label': '3 أشهر',
        },
        'semi': {
            'months': 6,
            'price': 1015,
            'discount': 15,
            'label': '6 أشهر',
        },
        'annual': {
            'months': 12,
            'price': 1791,
            'discount': 25,
            'label': 'سنوي',
        },
    }

    TRIAL_DAYS = 5

    # ─── Payment Link ───────────────────────────────────────────────

    def create_payment_link(self, agent, plan_key='monthly', is_trial=False):
        """
        Create a StreamPay payment link for subscription.
        
        Args:
            agent: Agent model instance
            plan_key: one of 'monthly', 'quarterly', 'semi', 'annual'
            is_trial: whether this is a trial subscription (charge after 5 days)
        
        Returns:
            dict with 'success', 'url', 'payment_link_id' or 'error'
        """
        plan = self.PLANS.get(plan_key)
        if not plan:
            return {'success': False, 'error': f'خطة غير صالحة: {plan_key}'}

        site_url = self._get_site_url()

        payload = {
            'name': f'اشتراك Inify Estate - {plan["label"]}',
            'description': f'اشتراك المسوق العقاري - {plan["label"]}',
            'items': [
                {
                    'product_id': self.product_ids.get(plan_key, self.product_ids.get('monthly', '')),
                    'quantity': 1,
                }
            ],
            'contact_information_type': 'PHONE',
            'currency': 'SAR',
            'max_number_of_payments': 1,
            'success_redirect_url': f'{site_url}/payment/success/',
            'failure_redirect_url': f'{site_url}/payment/failure/',
            'custom_metadata': {
                'agent_id': str(agent.id),
                'plan_key': plan_key,
                'is_trial': is_trial,
                'amount': plan['price'],
            },
        }

        try:
            response = requests.post(
                f'{STREAMPAY_BASE_URL}/payment_links',
                json=payload,
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Payment link created for agent {agent.id}: {data.get('id')}")
                return {
                    'success': True,
                    'url': data.get('url'),
                    'payment_link_id': data.get('id'),
                    'amount': plan['price'],
                }
            else:
                logger.error(f"StreamPay error: {response.status_code} - {response.text}")
                return {'success': False, 'error': f'خطأ في بوابة الدفع: {response.status_code}'}

        except requests.exceptions.RequestException as e:
            logger.error(f"StreamPay request error: {e}")
            return {'success': False, 'error': 'تعذر الاتصال ببوابة الدفع'}

    # ─── API: Fetch Invoice ─────────────────────────────────────────

    def get_invoice(self, invoice_id):
        """
        Fetch invoice details from StreamPay to verify payment.
        
        Args:
            invoice_id: StreamPay invoice UUID
        
        Returns:
            dict with invoice data or None
        """
        try:
            response = requests.get(
                f'{STREAMPAY_BASE_URL}/invoices/{invoice_id}',
                headers=self._get_headers(),
                timeout=30,
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Get invoice error: {response.status_code} - {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Get invoice request error: {e}")
            return None

    # ─── API: Fetch Subscription ──────────────────────────────────────

    def get_subscription(self, subscription_id):
        """
        Fetch subscription details from StreamPay.
        
        Args:
            subscription_id: StreamPay subscription UUID
        
        Returns:
            dict with subscription data or None
        """
        try:
            response = requests.get(
                f'{STREAMPAY_BASE_URL}/subscriptions/{subscription_id}',
                headers=self._get_headers(),
                timeout=30,
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Get subscription error: {response.status_code} - {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Get subscription request error: {e}")
            return None

    # ─── API: Cancel Subscription ─────────────────────────────────────

    def cancel_subscription(self, subscription_id):
        """
        Cancel a subscription in StreamPay.
        
        Args:
            subscription_id: StreamPay subscription UUID
        
        Returns:
            dict with 'success' and optional 'error'
        """
        try:
            response = requests.post(
                f'{STREAMPAY_BASE_URL}/subscriptions/{subscription_id}/cancel',
                headers=self._get_headers(),
                timeout=30,
            )
            if response.status_code == 200:
                logger.info(f"Subscription {subscription_id} cancelled")
                return {'success': True}
            else:
                logger.error(f"Cancel subscription error: {response.status_code} - {response.text}")
                return {'success': False, 'error': f'خطأ: {response.status_code}'}
        except requests.exceptions.RequestException as e:
            logger.error(f"Cancel subscription request error: {e}")
            return {'success': False, 'error': 'تعذر الاتصال ببوابة الدفع'}

    # ─── API: Create Consumer ─────────────────────────────────────────

    def create_or_get_consumer(self, agent):
        """
        Create a consumer in StreamPay for the agent (for recurring billing).
        
        Args:
            agent: Agent model instance
        
        Returns:
            dict with 'success', 'consumer_id' or 'error'
        """
        try:
            payload = {
                'name': f"{agent.user.first_name} {agent.user.last_name}".strip() or agent.user.username,
                'email': agent.email or agent.user.email,
                'phone': agent.phone or '',
            }

            response = requests.post(
                f'{STREAMPAY_BASE_URL}/consumers',
                json=payload,
                headers=self._get_headers(),
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                consumer_id = data.get('id', '')
                logger.info(f"Consumer created/found for agent {agent.id}: {consumer_id}")
                return {'success': True, 'consumer_id': consumer_id}
            else:
                logger.error(f"Create consumer error: {response.status_code} - {response.text}")
                return {'success': False, 'error': f'خطأ: {response.status_code}'}

        except requests.exceptions.RequestException as e:
            logger.error(f"Create consumer request error: {e}")
            return {'success': False, 'error': 'تعذر الاتصال ببوابة الدفع'}

    # ─── Webhook Verification ────────────────────────────────────────

    def verify_webhook_signature(self, raw_body, signature_header):
        """
        Verify StreamPay webhook signature.
        
        Args:
            raw_body: raw request body bytes
            signature_header: X-Webhook-Signature header value (t=TIMESTAMP,v1=SIGNATURE)
        
        Returns:
            bool
        """
        if not self.webhook_secret or not signature_header:
            return False

        try:
            parts = dict(x.split('=', 1) for x in signature_header.split(','))
            timestamp = parts.get('t', '')
            signature = parts.get('v1', '')

            message = f"{timestamp}.{raw_body.decode()}"
            computed = hmac.new(
                self.webhook_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(computed, signature)
        except Exception as e:
            logger.error(f"Webhook signature verification error: {e}")
            return False

    # ─── Trial Logic ─────────────────────────────────────────────────

    def get_trial_end_date(self, start_date=None):
        """Get the trial end date (5 days from start)"""
        start = start_date or timezone.now()
        return start + timedelta(days=self.TRIAL_DAYS)

    def get_subscription_end_date(self, plan_key, start_date=None):
        """Get subscription end date based on plan"""
        plan = self.PLANS.get(plan_key, self.PLANS['monthly'])
        start = start_date or timezone.now()
        if 'days' in plan:
            return start + timedelta(days=plan['days'])
        return start + timedelta(days=plan['months'] * 30)


# Singleton instance
streampay_service = StreamPayService()
