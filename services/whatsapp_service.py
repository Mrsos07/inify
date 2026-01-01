# -*- coding: utf-8 -*-
"""
WhatsApp Service - خدمة واتساب عبر Evolution API
"""

import os
import logging
import requests
from typing import Dict, Optional, Any
from django.conf import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """خدمة واتساب باستخدام Evolution API"""
    
    def __init__(self):
        self.base_url = os.getenv('EVOLUTION_API_URL', 'http://localhost:8080')
        self.api_key = os.getenv('EVOLUTION_API_KEY', '')
        self.headers = {
            'Content-Type': 'application/json',
            'apikey': self.api_key
        }
    
    @property
    def is_available(self) -> bool:
        """التحقق من توفر الخدمة"""
        return bool(self.api_key and self.base_url)
    
    def _make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """إجراء طلب HTTP"""
        url = f"{self.base_url}/{endpoint}"
        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=self.headers, timeout=30)
            else:
                return {'success': False, 'error': f'Unsupported method: {method}'}
            
            if response.status_code in [200, 201]:
                return {'success': True, 'data': response.json()}
            else:
                logger.error(f"Evolution API error: {response.status_code} - {response.text}")
                return {'success': False, 'error': response.text, 'status_code': response.status_code}
        except requests.exceptions.RequestException as e:
            logger.error(f"Evolution API request error: {e}")
            return {'success': False, 'error': str(e)}
    
    # ═══════════════════════════════════════════════════════════
    # إدارة الـ Instance
    # ═══════════════════════════════════════════════════════════
    
    def create_instance(self, instance_name: str, webhook_url: str = None) -> dict:
        """
        إنشاء instance جديد للواتساب
        
        Args:
            instance_name: اسم الـ instance (يجب أن يكون فريداً)
            webhook_url: رابط الـ webhook لاستقبال الرسائل
        
        Returns:
            dict مع معلومات الـ instance
        """
        data = {
            'instanceName': instance_name,
            'qrcode': True
        }
        
        result = self._make_request('POST', 'instance/create', data)
        
        if result.get('success'):
            logger.info(f"✅ WhatsApp instance created: {instance_name}")
        else:
            logger.error(f"❌ Failed to create WhatsApp instance: {result.get('error')}")
        
        return result
    
    def get_instance_status(self, instance_name: str) -> dict:
        """الحصول على حالة الـ instance"""
        return self._make_request('GET', f'instance/connectionState/{instance_name}')
    
    def get_qr_code(self, instance_name: str) -> dict:
        """
        الحصول على QR Code للربط
        Evolution API يرجع QR Code في base64 مع prefix: data:image/png;base64,...
        """
        result = self._make_request('GET', f'instance/connect/{instance_name}')
        
        if result.get('success'):
            data = result.get('data', {})
            # QR Code يأتي كاملاً مع data:image/png;base64, prefix
            qr_base64 = data.get('base64', '')
            logger.info(f"QR Code retrieved for {instance_name}, length: {len(qr_base64)}")
            return {
                'success': True,
                'base64': qr_base64,  # مباشرة في المستوى الأول
                'pairingCode': data.get('pairingCode'),
                'code': data.get('code')
            }
        
        return result
    
    def disconnect_instance(self, instance_name: str) -> dict:
        """قطع اتصال الـ instance"""
        return self._make_request('DELETE', f'instance/logout/{instance_name}')
    
    def delete_instance(self, instance_name: str) -> dict:
        """حذف الـ instance"""
        return self._make_request('DELETE', f'instance/delete/{instance_name}')
    
    def restart_instance(self, instance_name: str) -> dict:
        """إعادة تشغيل الـ instance"""
        return self._make_request('POST', f'instance/restart/{instance_name}')
    
    def set_webhook(self, instance_name: str, webhook_url: str) -> dict:
        """
        تسجيل Webhook لاستقبال الرسائل والأحداث
        
        Args:
            instance_name: اسم الـ instance
            webhook_url: رابط الـ webhook
        """
        data = {
            'url': webhook_url,
            'webhook_by_events': False,
            'webhook_base64': False,
            'events': [
                'MESSAGES_UPSERT',
                'CONNECTION_UPDATE',
                'QRCODE_UPDATED'
            ]
        }
        
        result = self._make_request('POST', f'webhook/set/{instance_name}', data)
        
        if result.get('success'):
            logger.info(f"✅ Webhook set for {instance_name}: {webhook_url}")
        else:
            logger.error(f"❌ Failed to set webhook: {result.get('error')}")
        
        return result
    
    # ═══════════════════════════════════════════════════════════
    # إرسال الرسائل
    # ═══════════════════════════════════════════════════════════
    
    def send_text_message(self, instance_name: str, phone_number: str, message: str) -> dict:
        """
        إرسال رسالة نصية
        
        Args:
            instance_name: اسم الـ instance
            phone_number: رقم الهاتف (مثل 966501234567)
            message: نص الرسالة
        """
        # تنسيق رقم الهاتف
        phone = self._format_phone_number(phone_number)
        
        data = {
            'number': phone,
            'text': message
        }
        
        result = self._make_request('POST', f'message/sendText/{instance_name}', data)
        
        if result.get('success'):
            logger.info(f"✅ WhatsApp message sent to {phone}")
        else:
            logger.error(f"❌ Failed to send WhatsApp message: {result.get('error')}")
        
        return result
    
    def send_media_message(self, instance_name: str, phone_number: str, 
                          media_url: str, media_type: str = 'image', 
                          caption: str = '') -> dict:
        """
        إرسال رسالة مع وسائط (صورة/فيديو/ملف)
        
        Args:
            instance_name: اسم الـ instance
            phone_number: رقم الهاتف
            media_url: رابط الوسائط
            media_type: نوع الوسائط (image, video, audio, document)
            caption: وصف الوسائط
        """
        phone = self._format_phone_number(phone_number)
        
        data = {
            'number': phone,
            'mediatype': media_type,
            'media': media_url,
            'caption': caption
        }
        
        return self._make_request('POST', f'message/sendMedia/{instance_name}', data)
    
    def send_buttons_message(self, instance_name: str, phone_number: str,
                            title: str, description: str, 
                            buttons: list, footer: str = '') -> dict:
        """
        إرسال رسالة مع أزرار
        
        Args:
            buttons: قائمة الأزرار [{'buttonId': 'id1', 'buttonText': {'displayText': 'نص'}}]
        """
        phone = self._format_phone_number(phone_number)
        
        data = {
            'number': phone,
            'title': title,
            'description': description,
            'footer': footer,
            'buttons': buttons
        }
        
        return self._make_request('POST', f'message/sendButtons/{instance_name}', data)
    
    def send_list_message(self, instance_name: str, phone_number: str,
                         title: str, description: str, button_text: str,
                         sections: list, footer: str = '') -> dict:
        """
        إرسال رسالة مع قائمة
        
        Args:
            sections: أقسام القائمة
        """
        phone = self._format_phone_number(phone_number)
        
        data = {
            'number': phone,
            'title': title,
            'description': description,
            'buttonText': button_text,
            'footerText': footer,
            'sections': sections
        }
        
        return self._make_request('POST', f'message/sendList/{instance_name}', data)
    
    # ═══════════════════════════════════════════════════════════
    # إعدادات الـ Webhook
    # ═══════════════════════════════════════════════════════════
    
    def set_webhook(self, instance_name: str, webhook_url: str, events: list = None) -> dict:
        """
        تعيين رابط الـ webhook
        
        Args:
            instance_name: اسم الـ instance
            webhook_url: رابط الـ webhook
            events: قائمة الأحداث للاستماع لها
        """
        if events is None:
            events = [
                'MESSAGES_UPSERT',
                'MESSAGES_UPDATE', 
                'CONNECTION_UPDATE',
                'QRCODE_UPDATED'
            ]
        
        data = {
            'webhook': {
                'enabled': True,
                'url': webhook_url,
                'events': events
            }
        }
        
        return self._make_request('POST', f'webhook/set/{instance_name}', data)
    
    def get_webhook_config(self, instance_name: str) -> dict:
        """الحصول على إعدادات الـ webhook"""
        return self._make_request('GET', f'webhook/find/{instance_name}')
    
    # ═══════════════════════════════════════════════════════════
    # دوال مساعدة
    # ═══════════════════════════════════════════════════════════
    
    def _format_phone_number(self, phone: str) -> str:
        """
        تنسيق رقم الهاتف للواتساب
        
        - إزالة + والمسافات
        - إضافة @s.whatsapp.net
        """
        # إزالة الرموز غير الرقمية
        phone = ''.join(filter(str.isdigit, phone))
        
        # إضافة رمز السعودية إذا لم يكن موجوداً
        if phone.startswith('05'):
            phone = '966' + phone[1:]
        elif phone.startswith('5'):
            phone = '966' + phone
        
        return f"{phone}@s.whatsapp.net"
    
    def parse_webhook_message(self, webhook_data: dict) -> Optional[Dict[str, Any]]:
        """
        تحليل رسالة الـ webhook الواردة
        
        Returns:
            dict مع معلومات الرسالة أو None
        """
        try:
            event = webhook_data.get('event')
            instance = webhook_data.get('instance')
            data = webhook_data.get('data', {})
            
            if event == 'messages.upsert':
                messages = data.get('messages', [])
                if messages:
                    msg = messages[0]
                    key = msg.get('key', {})
                    
                    # تجاهل الرسائل الصادرة
                    if key.get('fromMe'):
                        return None
                    
                    # استخراج محتوى الرسالة
                    message_content = msg.get('message', {})
                    text = (
                        message_content.get('conversation') or
                        message_content.get('extendedTextMessage', {}).get('text') or
                        message_content.get('buttonsResponseMessage', {}).get('selectedDisplayText') or
                        message_content.get('listResponseMessage', {}).get('title') or
                        ''
                    )
                    
                    # استخراج رقم الهاتف
                    remote_jid = key.get('remoteJid', '')
                    phone = remote_jid.replace('@s.whatsapp.net', '').replace('@g.us', '')
                    
                    # اسم المرسل
                    push_name = msg.get('pushName', '')
                    
                    return {
                        'event': 'message',
                        'instance': instance,
                        'message_id': key.get('id'),
                        'phone': phone,
                        'sender_name': push_name,
                        'text': text,
                        'is_group': '@g.us' in remote_jid,
                        'timestamp': msg.get('messageTimestamp'),
                        'raw': msg
                    }
            
            elif event == 'connection.update':
                state = data.get('state')
                return {
                    'event': 'connection',
                    'instance': instance,
                    'state': state,
                    'raw': data
                }
            
            elif event == 'qrcode.updated':
                return {
                    'event': 'qrcode',
                    'instance': instance,
                    'qrcode': data.get('qrcode', {}).get('base64'),
                    'raw': data
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing webhook message: {e}")
            return None
    
    def get_diagnostic_info(self) -> dict:
        """معلومات تشخيصية"""
        return {
            'is_available': self.is_available,
            'base_url': self.base_url,
            'api_key_set': bool(self.api_key)
        }


# Singleton instance
whatsapp_service = WhatsAppService()
