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
        إنشاء instance جديد للواتساب - Evolution API v2.2.x
        """
        data = {
            'instanceName': instance_name,
            'integration': 'WHATSAPP-BAILEYS',
            'token': instance_name,
            'qrcode': True
        }
        
        result = self._make_request('POST', 'instance/create', data)
        
        if result.get('success'):
            logger.info(f"WhatsApp instance created: {instance_name}")
            if webhook_url:
                self.set_webhook(instance_name, webhook_url)
        else:
            logger.error(f"Failed to create WhatsApp instance: {result.get('error')}")
        
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
        تسجيل Webhook لاستقبال الرسائل - Evolution API v2.2.x
        تفعيل جميع الأحداث المهمة للرد على المرسل الصحيح
        """
        data = {
            'webhook': {
                'enabled': True,
                'url': webhook_url,
                'webhookByEvents': False,
                'webhookBase64': False,
                'events': [
                    'MESSAGES_UPSERT',
                    'MESSAGES_UPDATE',
                    'SEND_MESSAGE',
                    'CONNECTION_UPDATE',
                    'QRCODE_UPDATED',
                    'CONTACTS_UPSERT',
                    'CONTACTS_UPDATE',
                    'CHATS_UPSERT',
                    'CHATS_UPDATE'
                ]
            }
        }
        
        logger.info(f"Setting webhook for {instance_name}: {webhook_url}")
        result = self._make_request('POST', f'webhook/set/{instance_name}', data)
        
        if result.get('success'):
            logger.info(f"Webhook set successfully for {instance_name}")
        else:
            logger.error(f"Failed to set webhook: {result.get('error')}")
        
        return result
    
    # Cache لحفظ mapping بين LID ورقم الهاتف
    _lid_phone_cache: dict = {}
    
    def _resolve_lid_to_phone(self, instance_name: str, lid: str, push_name: str = '') -> Optional[str]:
        """
        تحويل LID إلى رقم هاتف حقيقي
        1. البحث في ملف lid_phone_mapping.json
        2. البحث في الـ cache
        3. مطابقة createdAt بين LID contact و phone contact
        """
        import json
        import os
        
        try:
            lid_jid = lid if '@lid' in lid else f"{lid}@lid"
            lid_number = lid_jid.replace('@lid', '')
            print(f"[RESOLVE] LID: {lid_number}, pushName: {push_name}")
            
            # 1. البحث في ملف الـ mapping أولاً
            mapping_file = os.path.join(os.path.dirname(__file__), '..', 'lid_phone_mapping.json')
            if os.path.exists(mapping_file):
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    mappings = data.get('mappings', {})
                    if lid_number in mappings and mappings[lid_number]:
                        phone = mappings[lid_number]
                        print(f"[RESOLVE] ✅ From mapping file: {phone}")
                        return phone
            
            # 2. البحث في الـ cache
            cache_key = f"{instance_name}:{lid_jid}"
            if cache_key in self._lid_phone_cache:
                print(f"[RESOLVE] ✅ From cache: {self._lid_phone_cache[cache_key]}")
                return self._lid_phone_cache[cache_key]
            
            # 3. جلب الـ contacts ومطابقة createdAt
            contacts_result = self._make_request('POST', f'chat/findContacts/{instance_name}', {})
            if not contacts_result.get('success'):
                print(f"[RESOLVE] ❌ Failed to get contacts")
                return None
            
            contacts = contacts_result.get('data', [])
            
            # إيجاد الـ LID contact
            lid_contact = None
            for c in contacts:
                if c.get('remoteJid') == lid_jid:
                    lid_contact = c
                    break
            
            if not lid_contact:
                print(f"[RESOLVE] ❌ LID not in contacts")
                return None
            
            lid_created_at = lid_contact.get('createdAt', '')
            
            # البحث عن phone contact بنفس createdAt
            for c in contacts:
                remote_jid = c.get('remoteJid', '')
                if '@s.whatsapp.net' in remote_jid and '@lid' not in remote_jid:
                    if c.get('createdAt') == lid_created_at:
                        phone = remote_jid.replace('@s.whatsapp.net', '')
                        self._lid_phone_cache[cache_key] = phone
                        print(f"[RESOLVE] ✅ Matched by createdAt: {phone}")
                        return phone
            
            print(f"[RESOLVE] ❌ No phone found - add to lid_phone_mapping.json")
            return None
        except Exception as e:
            print(f"[RESOLVE] Error: {e}")
            return None
    
    def cache_lid_phone_mapping(self, instance_name: str, lid: str, phone: str):
        """حفظ mapping بين LID ورقم الهاتف"""
        cache_key = f"{instance_name}:{lid}"
        self._lid_phone_cache[cache_key] = phone
        print(f"[CACHE] Stored mapping: {lid} -> {phone}")
    
    # ═══════════════════════════════════════════════════════════
    # إرسال الرسائل
    # ═══════════════════════════════════════════════════════════
    
    def send_text_message(self, instance_name: str, phone_number: str, message: str) -> dict:
        """
        إرسال رسالة نصية - بسيط وديناميكي
        
        Args:
            instance_name: اسم الـ instance
            phone_number: رقم الهاتف المستخرج من remoteJid
            message: نص الرسالة
        """
        # تنسيق رقم الهاتف - أرقام فقط
        phone = ''.join(filter(str.isdigit, str(phone_number)))
        
        # إضافة رمز السعودية إذا كان رقم محلي
        if phone.startswith('05'):
            phone = '966' + phone[1:]
        elif phone.startswith('5') and len(phone) == 9:
            phone = '966' + phone
        
        print(f"[SEND] Sending to: {phone}")
        
        # صيغة Evolution API v2.x
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
        تحليل رسالة الـ webhook الواردة من Evolution API
        
        Returns:
            dict مع معلومات الرسالة أو None
        """
        try:
            event = webhook_data.get('event')
            instance = webhook_data.get('instance')
            
            logger.info(f"Parsing webhook - Event: {event}")
            
            # تحويل اسم الحدث لأحرف صغيرة للمقارنة
            event_lower = event.lower() if event else ''
            
            if event_lower == 'messages.upsert' or event == 'MESSAGES_UPSERT':
                # Evolution API v2.x - البيانات في data object
                data = webhook_data.get('data', {})
                
                # استخراج key و message
                key = data.get('key', {})
                message_content = data.get('message', {})
                push_name = data.get('pushName', '')
                
                # تجاهل الرسائل الصادرة
                if key.get('fromMe'):
                    return None
                
                # ══════════════════════════════════════════════════════
                # استخراج رقم المرسل - بسيط وديناميكي
                # ══════════════════════════════════════════════════════
                remote_jid = key.get('remoteJid', '')
                
                # التحقق من نوع المحادثة
                if '@g.us' in remote_jid:
                    # رسالة في مجموعة - نستخدم participant
                    participant = key.get('participant', '')
                    phone = participant.split('@')[0] if participant else ''
                    is_group = True
                else:
                    # رسالة فردية - نستخدم remoteJid مباشرة
                    # يعمل مع @s.whatsapp.net و @lid
                    phone = remote_jid.split('@')[0] if remote_jid else ''
                    is_group = False
                
                print(f"[PARSE] Message from: {phone}, remoteJid: {remote_jid}")
                
                # استخراج محتوى الرسالة
                text = (
                    message_content.get('conversation') or
                    message_content.get('extendedTextMessage', {}).get('text') or
                    message_content.get('buttonsResponseMessage', {}).get('selectedDisplayText') or
                    message_content.get('listResponseMessage', {}).get('title') or
                    ''
                )
                
                # التأكد من أن الرقم صالح (أرقام فقط)
                phone = ''.join(filter(str.isdigit, phone))
                if not phone or len(phone) < 10:
                    print(f"[PARSE] Invalid phone number: {phone}")
                    return None
                
                print(f"[PARSE] Final phone: {phone}, is_group: {is_group}")
                
                return {
                    'event': 'message',
                    'instance': instance,
                    'message_id': key.get('id'),
                    'phone': phone,
                    'sender_name': push_name,
                    'text': text,
                    'is_group': is_group,
                    'timestamp': data.get('messageTimestamp', webhook_data.get('date_time')),
                    'raw': webhook_data
                }
            
            elif event_lower == 'connection.update' or event == 'CONNECTION_UPDATE':
                data = webhook_data.get('data', {})
                state = data.get('state', webhook_data.get('state'))
                return {
                    'event': 'connection',
                    'instance': instance,
                    'state': state,
                    'raw': data
                }
            
            elif event_lower == 'qrcode.updated' or event == 'QRCODE_UPDATED':
                data = webhook_data.get('data', {})
                qr_base64 = data.get('qrcode', {}).get('base64') or webhook_data.get('qrcode', {}).get('base64', '')
                return {
                    'event': 'qrcode',
                    'instance': instance,
                    'qrcode': qr_base64,
                    'raw': data
                }
            
            elif event_lower == 'contacts.upsert' or event == 'CONTACTS_UPSERT':
                data = webhook_data.get('data', [])
                return {
                    'event': 'contacts',
                    'instance': instance,
                    'contacts': data if isinstance(data, list) else [data],
                    'raw': webhook_data
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
