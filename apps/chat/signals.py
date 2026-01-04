# -*- coding: utf-8 -*-
"""
Signals - إشارات لإرسال التحديثات الفورية عبر WebSocket
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Message

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Message)
def broadcast_new_message(sender, instance, created, **kwargs):
    """
    بث رسالة جديدة عبر WebSocket
    يتم تشغيله تلقائياً عند حفظ رسالة جديدة
    """
    if not created:
        return
    
    try:
        conversation = instance.conversation
        agent_id = str(conversation.agent.id)
        
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        
        # إرسال إلى مجموعة الوكيل
        async_to_sync(channel_layer.group_send)(
            f'whatsapp_agent_{agent_id}',
            {
                'type': 'new_message',
                'conversation_id': str(conversation.id),
                'phone': conversation.client_phone,
                'sender_name': conversation.client_name,
                'message': instance.content,
                'role': instance.role,
                'timestamp': instance.created_at.isoformat()
            }
        )
        
        logger.info(f"📡 Broadcasted message to agent {agent_id}")
    
    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
