# -*- coding: utf-8 -*-
"""
Agents Views - واجهات برمجة المسوقين العقاريين
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Agent, AgentSettings
from .serializers import AgentSerializer, AgentSettingsSerializer


class AgentViewSet(viewsets.ModelViewSet):
    """ViewSet للمسوقين العقاريين"""
    
    serializer_class = AgentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """الحصول على بيانات المسوق الحالي فقط"""
        if hasattr(self.request.user, 'agent_profile'):
            return Agent.objects.filter(id=self.request.user.agent_profile.id)
        return Agent.objects.none()
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """الحصول على بيانات المسوق الحالي"""
        if hasattr(request.user, 'agent_profile'):
            serializer = self.get_serializer(request.user.agent_profile)
            return Response(serializer.data)
        return Response(
            {'error': 'لا يوجد ملف مسوق مرتبط بهذا الحساب'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    @action(detail=False, methods=['get', 'put', 'patch'])
    def settings(self, request):
        """إدارة إعدادات المسوق"""
        if not hasattr(request.user, 'agent_profile'):
            return Response(
                {'error': 'لا يوجد ملف مسوق مرتبط بهذا الحساب'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        agent = request.user.agent_profile
        settings_obj, created = AgentSettings.objects.get_or_create(agent=agent)
        
        if request.method == 'GET':
            serializer = AgentSettingsSerializer(settings_obj)
            return Response(serializer.data)
        
        serializer = AgentSettingsSerializer(settings_obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """لوحة تحكم المسوق"""
        if not hasattr(request.user, 'agent_profile'):
            return Response(
                {'error': 'لا يوجد ملف مسوق مرتبط بهذا الحساب'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        agent = request.user.agent_profile
        
        from apps.properties.models import Property
        from apps.leads.models import Lead
        from apps.chat.models import Conversation
        from django.utils import timezone
        from datetime import timedelta
        
        # إحصائيات العقارات
        properties = Property.objects.filter(agent=agent, is_active=True)
        properties_stats = {
            'total': properties.count(),
            'for_sale': properties.filter(status='for_sale').count(),
            'for_rent': properties.filter(status='for_rent').count(),
            'featured': properties.filter(is_featured=True).count(),
        }
        
        # إحصائيات العملاء
        leads = Lead.objects.filter(agent=agent)
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        leads_stats = {
            'total': leads.count(),
            'new': leads.filter(status='new').count(),
            'this_week': leads.filter(created_at__date__gte=week_ago).count(),
            'hot': leads.filter(urgency='immediate').count(),
        }
        
        # إحصائيات المحادثات
        conversations = Conversation.objects.filter(agent=agent)
        conversations_stats = {
            'total': conversations.count(),
            'active': conversations.filter(status='active').count(),
            'this_week': conversations.filter(started_at__date__gte=week_ago).count(),
        }
        
        # آخر العملاء
        recent_leads = leads.order_by('-created_at')[:5]
        recent_leads_data = [
            {
                'id': str(l.id),
                'name': l.name,
                'status': l.get_status_display(),
                'created_at': l.created_at.isoformat()
            }
            for l in recent_leads
        ]
        
        return Response({
            'properties': properties_stats,
            'leads': leads_stats,
            'conversations': conversations_stats,
            'recent_leads': recent_leads_data
        })
