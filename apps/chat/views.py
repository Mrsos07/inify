# -*- coding: utf-8 -*-
"""
Chat Views - واجهات برمجة المحادثات
"""

import json
import logging
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from .models import Conversation, Message, ConversationSummary
from .serializers import ConversationSerializer, MessageSerializer
from services.ai_service import NewraAIService
from services.rag_service import RAGService
from services.gemini_service import GeminiService

logger = logging.getLogger(__name__)


class ChatViewSet(viewsets.ModelViewSet):
    """ViewSet للمحادثات"""
    
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """الحصول على محادثات المسوق الحالي فقط"""
        if hasattr(self.request.user, 'agent_profile'):
            return Conversation.objects.filter(agent=self.request.user.agent_profile)
        return Conversation.objects.none()
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """الحصول على رسائل محادثة معينة"""
        conversation = self.get_object()
        messages = conversation.messages.all()
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """إرسال رسالة في محادثة"""
        conversation = self.get_object()
        content = request.data.get('content', '')
        
        if not content:
            return Response(
                {'error': 'محتوى الرسالة مطلوب'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # حفظ رسالة المستخدم
        user_message = Message.objects.create(
            conversation=conversation,
            role='user',
            content=content
        )
        
        # الحصول على رد AI
        ai_service = NewraAIService(agent=conversation.agent)
        messages = conversation.get_messages_for_ai()
        
        response = ai_service.chat(
            messages=messages,
            conversation_context=conversation.context,
            language=conversation.language
        )
        
        # حفظ رد المساعد
        assistant_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=response['content'],
            tool_calls=response.get('tool_calls'),
            tool_results=response.get('tool_results'),
            model_used=response.get('model', ''),
            tokens_used=response.get('tokens', {}).get('total', 0)
        )
        
        # تحديث عداد الرسائل
        conversation.messages_count = conversation.messages.count()
        conversation.save()
        
        return Response({
            'user_message': MessageSerializer(user_message).data,
            'assistant_message': MessageSerializer(assistant_message).data
        })
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """إغلاق المحادثة"""
        conversation = self.get_object()
        conversation.status = 'closed'
        conversation.save()
        
        # إنشاء ملخص
        ai_service = NewraAIService(agent=conversation.agent)
        messages = conversation.get_messages_for_ai(limit=50)
        summary_data = ai_service.generate_conversation_summary(messages)
        
        if summary_data:
            ConversationSummary.objects.update_or_create(
                conversation=conversation,
                defaults={
                    'summary': summary_data.get('summary', ''),
                    'key_points': summary_data.get('key_points', []),
                    'client_intent': summary_data.get('client_intent', ''),
                    'lead_quality': summary_data.get('lead_quality', 'cold')
                }
            )
        
        return Response({'status': 'closed'})


@method_decorator(csrf_exempt, name='dispatch')
class PublicChatView(View):
    """واجهة الشات العامة (للموقع)"""
    
    def post(self, request):
        """معالجة رسالة جديدة"""
        try:
            data = json.loads(request.body)
            
            agent_id = data.get('agent_id')
            client_id = data.get('client_id')
            message = data.get('message', '')
            conversation_id = data.get('conversation_id')
            
            if not agent_id or not message:
                return JsonResponse({
                    'error': 'agent_id و message مطلوبان'
                }, status=400)
            
            # الحصول على المسوق
            from apps.agents.models import Agent
            try:
                agent = Agent.objects.get(id=agent_id, is_active=True)
            except Agent.DoesNotExist:
                return JsonResponse({
                    'error': 'المسوق غير موجود'
                }, status=404)
            
            # الحصول على أو إنشاء المحادثة
            if conversation_id:
                try:
                    conversation = Conversation.objects.get(
                        id=conversation_id,
                        agent=agent
                    )
                except Conversation.DoesNotExist:
                    conversation = None
            else:
                conversation = None
            
            if not conversation:
                conversation = Conversation.objects.create(
                    agent=agent,
                    client_id=client_id or f"web_{request.META.get('REMOTE_ADDR', 'unknown')}",
                    source='website',
                    language=data.get('language', 'ar'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    ip_address=self._get_client_ip(request)
                )
            
            # حفظ رسالة المستخدم
            user_message = Message.objects.create(
                conversation=conversation,
                role='user',
                content=message
            )
            
            # استخدام RAG مع Gemini للبحث الذكي
            rag_service = RAGService()
            gemini_service = GeminiService(agent=agent)
            
            # الحصول على سياق العقارات
            properties_context = rag_service.get_property_context(str(agent.id), message)
            
            # الحصول على تاريخ المحادثة
            chat_history = [
                {'role': msg.role, 'content': msg.content}
                for msg in conversation.messages.order_by('created_at')[:10]
            ]
            
            # توليد الرد باستخدام Gemini مع RAG
            if gemini_service.is_available:
                response = gemini_service.chat_with_context(
                    user_message=message,
                    properties_context=properties_context,
                    chat_history=chat_history
                )
            else:
                # استخدام OpenAI كبديل
                ai_service = NewraAIService(agent=agent)
                messages = conversation.get_messages_for_ai()
                response = ai_service.chat(
                    messages=messages,
                    conversation_context=conversation.context,
                    language=conversation.language
                )
            
            # الحصول على العقارات المقترحة
            rag_response = rag_service.generate_property_response(str(agent.id), message)
            suggested_properties = rag_response.get('suggested_properties', [])
            
            # حفظ رد المساعد
            assistant_message = Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=response['content'],
                tool_calls=response.get('tool_calls'),
                tool_results=response.get('tool_results'),
                model_used=response.get('model', 'gemini-1.5-flash'),
                tokens_used=response.get('tokens', {}).get('total', 0)
            )
            
            # تحديث المحادثة
            conversation.messages_count = conversation.messages.count()
            conversation.save()
            
            return JsonResponse({
                'conversation_id': str(conversation.id),
                'response': response['content'],
                'suggested_properties': suggested_properties,
                'message_id': str(assistant_message.id),
                'has_properties': len(suggested_properties) > 0
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'بيانات JSON غير صالحة'
            }, status=400)
        except Exception as e:
            logger.error(f"Public chat error: {str(e)}")
            return JsonResponse({
                'error': 'حدث خطأ في معالجة الطلب'
            }, status=500)
    
    def _get_client_ip(self, request):
        """الحصول على IP العميل"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


@method_decorator(csrf_exempt, name='dispatch')
class WebhookView(View):
    """واجهة Webhook لـ n8n والتكاملات الخارجية"""
    
    def post(self, request):
        """معالجة طلب Webhook"""
        try:
            data = json.loads(request.body)
            
            # التحقق من المفتاح السري
            secret = request.headers.get('X-Webhook-Secret')
            agent_id = data.get('agent_id')
            
            if not agent_id:
                return JsonResponse({
                    'error': 'agent_id مطلوب'
                }, status=400)
            
            from apps.agents.models import Agent
            try:
                agent = Agent.objects.get(id=agent_id, is_active=True)
            except Agent.DoesNotExist:
                return JsonResponse({
                    'error': 'المسوق غير موجود'
                }, status=404)
            
            # التحقق من المفتاح
            if agent.webhook_secret and agent.webhook_secret != secret:
                return JsonResponse({
                    'error': 'مفتاح غير صالح'
                }, status=403)
            
            # معالجة حسب نوع الحدث
            event_type = data.get('event', 'message')
            
            if event_type == 'message':
                return self._handle_message(agent, data)
            elif event_type == 'whatsapp':
                return self._handle_whatsapp(agent, data)
            else:
                return JsonResponse({
                    'error': f'نوع حدث غير معروف: {event_type}'
                }, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'بيانات JSON غير صالحة'
            }, status=400)
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return JsonResponse({
                'error': 'حدث خطأ في معالجة الطلب'
            }, status=500)
    
    def _handle_message(self, agent, data):
        """معالجة رسالة عادية"""
        message = data.get('message', '')
        client_id = data.get('client_id', 'webhook')
        conversation_id = data.get('conversation_id')
        
        if not message:
            return JsonResponse({
                'error': 'message مطلوب'
            }, status=400)
        
        # الحصول على أو إنشاء المحادثة
        if conversation_id:
            try:
                conversation = Conversation.objects.get(
                    id=conversation_id,
                    agent=agent
                )
            except Conversation.DoesNotExist:
                conversation = None
        else:
            conversation = None
        
        if not conversation:
            conversation = Conversation.objects.create(
                agent=agent,
                client_id=client_id,
                source='api'
            )
        
        # حفظ الرسالة والحصول على الرد
        Message.objects.create(
            conversation=conversation,
            role='user',
            content=message
        )
        
        ai_service = NewraAIService(agent=agent)
        messages = conversation.get_messages_for_ai()
        response = ai_service.chat(messages=messages)
        
        Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=response['content']
        )
        
        return JsonResponse({
            'conversation_id': str(conversation.id),
            'response': response['content']
        })
    
    def _handle_whatsapp(self, agent, data):
        """معالجة رسالة واتساب"""
        message = data.get('message', '')
        phone = data.get('phone', '')
        name = data.get('name', '')
        
        if not message or not phone:
            return JsonResponse({
                'error': 'message و phone مطلوبان'
            }, status=400)
        
        # البحث عن محادثة موجودة أو إنشاء جديدة
        conversation = Conversation.objects.filter(
            agent=agent,
            client_phone=phone,
            source='whatsapp',
            status='active'
        ).first()
        
        if not conversation:
            conversation = Conversation.objects.create(
                agent=agent,
                client_id=phone,
                client_name=name,
                client_phone=phone,
                source='whatsapp'
            )
        
        # حفظ الرسالة والحصول على الرد
        Message.objects.create(
            conversation=conversation,
            role='user',
            content=message
        )
        
        ai_service = NewraAIService(agent=agent)
        messages = conversation.get_messages_for_ai()
        response = ai_service.chat(messages=messages)
        
        Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=response['content']
        )
        
        return JsonResponse({
            'conversation_id': str(conversation.id),
            'response': response['content'],
            'phone': phone
        })
