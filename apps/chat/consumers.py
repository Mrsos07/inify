# -*- coding: utf-8 -*-
"""
WebSocket Consumers - للاتصال الفوري مع المحادثات
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class WhatsAppConversationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket Consumer لمتابعة المحادثات الحية
    يتيح للمانيجر متابعة جميع المحادثات في الوقت الفعلي
    """
    
    async def connect(self):
        """الاتصال بالـ WebSocket"""
        self.agent_id = self.scope['url_route']['kwargs']['agent_id']
        self.room_group_name = f'whatsapp_agent_{self.agent_id}'
        
        # الانضمام إلى المجموعة
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"✅ WebSocket connected for agent {self.agent_id}")
        
        # إرسال رسالة ترحيب
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'متصل بنجاح',
            'agent_id': self.agent_id
        }))
    
    async def disconnect(self, close_code):
        """قطع الاتصال"""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"❌ WebSocket disconnected for agent {self.agent_id}")
    
    async def receive(self, text_data):
        """استقبال رسالة من العميل"""
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'get_active_sessions':
                # الحصول على الجلسات النشطة
                sessions = await self.get_active_sessions()
                await self.send(text_data=json.dumps({
                    'type': 'active_sessions',
                    'sessions': sessions
                }))
            
            elif action == 'get_conversation':
                # الحصول على محادثة معينة
                conversation_id = data.get('conversation_id')
                conversation = await self.get_conversation_details(conversation_id)
                await self.send(text_data=json.dumps({
                    'type': 'conversation_details',
                    'conversation': conversation
                }))
            
            elif action == 'send_message':
                # إرسال رسالة من المانيجر
                conversation_id = data.get('conversation_id')
                message = data.get('message')
                result = await self.send_manager_message(conversation_id, message)
                await self.send(text_data=json.dumps({
                    'type': 'message_sent',
                    'result': result
                }))
        
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def new_message(self, event):
        """إرسال رسالة جديدة إلى العميل"""
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'conversation_id': event['conversation_id'],
            'phone': event['phone'],
            'sender_name': event['sender_name'],
            'message': event['message'],
            'role': event['role'],
            'timestamp': event['timestamp']
        }))
    
    async def conversation_update(self, event):
        """تحديث حالة المحادثة"""
        await self.send(text_data=json.dumps({
            'type': 'conversation_update',
            'conversation_id': event['conversation_id'],
            'status': event['status'],
            'data': event.get('data', {})
        }))
    
    @database_sync_to_async
    def get_active_sessions(self):
        """الحصول على الجلسات النشطة"""
        from apps.chat.models import Conversation
        from apps.agents.models import Agent
        
        try:
            agent = Agent.objects.get(id=self.agent_id)
            conversations = Conversation.objects.filter(
                agent=agent,
                source='whatsapp',
                status='active'
            ).order_by('-last_message_at')[:20]
            
            return [{
                'id': str(conv.id),
                'phone': conv.client_phone,
                'name': conv.client_name,
                'message_count': conv.messages_count,
                'last_message': conv.last_message_at.isoformat() if conv.last_message_at else None
            } for conv in conversations]
        except Exception as e:
            logger.error(f"Error getting active sessions: {e}")
            return []
    
    @database_sync_to_async
    def get_conversation_details(self, conversation_id):
        """الحصول على تفاصيل محادثة"""
        from apps.chat.models import Conversation, Message
        
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            messages = conversation.messages.order_by('created_at')[:50]
            
            return {
                'id': str(conversation.id),
                'phone': conversation.client_phone,
                'name': conversation.client_name,
                'status': conversation.status,
                'messages': [{
                    'id': str(msg.id),
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.created_at.isoformat()
                } for msg in messages]
            }
        except Exception as e:
            logger.error(f"Error getting conversation: {e}")
            return None
    
    @database_sync_to_async
    def send_manager_message(self, conversation_id, message):
        """إرسال رسالة من المانيجر"""
        from apps.chat.models import Conversation, Message
        from services.whatsapp_service import whatsapp_service
        from apps.agents.models import WhatsAppInstance
        
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            
            # حفظ الرسالة
            Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=message
            )
            
            # إرسال عبر واتساب
            wa_instance = WhatsAppInstance.objects.get(agent=conversation.agent)
            result = whatsapp_service.send_text_message(
                instance_name=wa_instance.instance_name,
                phone_number=conversation.client_phone,
                message=message
            )
            
            return {
                'success': result.get('success', False),
                'message': 'تم الإرسال بنجاح' if result.get('success') else 'فشل الإرسال'
            }
        except Exception as e:
            logger.error(f"Error sending manager message: {e}")
            return {'success': False, 'message': str(e)}
