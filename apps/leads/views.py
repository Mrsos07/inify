# -*- coding: utf-8 -*-
"""
Leads Views - واجهات برمجة العملاء المحتملين
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from django_filters.rest_framework import DjangoFilterBackend

from .models import Lead, LeadActivity, ViewingAppointment
from .serializers import (
    LeadSerializer, LeadDetailSerializer, LeadCreateSerializer,
    LeadActivitySerializer, ViewingAppointmentSerializer
)
from services.lead_service import LeadService


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session authentication without CSRF check"""
    def enforce_csrf(self, request):
        return  # Skip CSRF check


class LeadViewSet(viewsets.ModelViewSet):
    """ViewSet للعملاء المحتملين"""
    
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'source', 'urgency', 'looking_for']
    search_fields = ['name', 'phone', 'email', 'city_preference']
    ordering_fields = ['created_at', 'score', 'last_contact_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """الحصول على عملاء المسوق الحالي فقط"""
        if hasattr(self.request.user, 'agent_profile'):
            return Lead.objects.filter(agent=self.request.user.agent_profile)
        return Lead.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LeadDetailSerializer
        elif self.action == 'create':
            return LeadCreateSerializer
        return LeadSerializer
    
    def perform_create(self, serializer):
        """إنشاء عميل محتمل جديد"""
        lead = serializer.save(agent=self.request.user.agent_profile)
        lead.calculate_score()
        lead.save()
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """تحديث حالة العميل"""
        lead = self.get_object()
        new_status = request.data.get('status')
        notes = request.data.get('notes', '')
        
        if not new_status:
            return Response(
                {'error': 'الحالة الجديدة مطلوبة'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        service = LeadService(agent=self.request.user.agent_profile)
        result = service.update_lead_status(str(lead.id), new_status, notes)
        
        return Response(result)
    
    @action(detail=True, methods=['get'])
    def activities(self, request, pk=None):
        """الحصول على سجل أنشطة العميل"""
        lead = self.get_object()
        activities = lead.activities.all()
        serializer = LeadActivitySerializer(activities, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_note(self, request, pk=None):
        """إضافة ملاحظة للعميل"""
        lead = self.get_object()
        note = request.data.get('note', '')
        
        if not note:
            return Response(
                {'error': 'الملاحظة مطلوبة'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from datetime import datetime
        lead.notes = f"{lead.notes}\n\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}]: {note}"
        lead.save()
        
        LeadActivity.objects.create(
            lead=lead,
            activity_type='note_added',
            description=note
        )
        
        return Response({'status': 'تمت إضافة الملاحظة'})
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """إحصائيات العملاء المحتملين"""
        from django.db.models import Count
        
        queryset = self.get_queryset()
        
        stats = {
            'total': queryset.count(),
            'by_status': {},
            'by_source': {},
            'by_urgency': {},
            'average_score': 0
        }
        
        # إحصائيات حسب الحالة
        status_stats = queryset.values('status').annotate(count=Count('id'))
        for item in status_stats:
            from .models import LeadStatus
            status_display = dict(LeadStatus.choices).get(item['status'], item['status'])
            stats['by_status'][status_display] = item['count']
        
        # إحصائيات حسب المصدر
        source_stats = queryset.values('source').annotate(count=Count('id'))
        for item in source_stats:
            from .models import LeadSource
            source_display = dict(LeadSource.choices).get(item['source'], item['source'])
            stats['by_source'][source_display] = item['count']
        
        # متوسط التقييم
        from django.db.models import Avg
        avg = queryset.aggregate(avg_score=Avg('score'))
        stats['average_score'] = round(avg['avg_score'] or 0, 1)
        
        return Response(stats)


class ViewingAppointmentViewSet(viewsets.ModelViewSet):
    """ViewSet لمواعيد المعاينة"""
    
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ViewingAppointmentSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'scheduled_date']
    ordering = ['scheduled_date', 'scheduled_time']
    
    def get_queryset(self):
        """الحصول على مواعيد المسوق الحالي فقط"""
        if hasattr(self.request.user, 'agent_profile'):
            return ViewingAppointment.objects.filter(
                lead__agent=self.request.user.agent_profile
            )
        return ViewingAppointment.objects.none()
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """تأكيد الموعد"""
        appointment = self.get_object()
        appointment.status = 'confirmed'
        appointment.save()
        return Response({'status': 'تم تأكيد الموعد'})
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """إلغاء الموعد"""
        appointment = self.get_object()
        appointment.status = 'cancelled'
        appointment.notes = f"{appointment.notes}\nسبب الإلغاء: {request.data.get('reason', 'غير محدد')}"
        appointment.save()
        return Response({'status': 'تم إلغاء الموعد'})
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """إكمال الموعد"""
        appointment = self.get_object()
        appointment.status = 'completed'
        appointment.feedback = request.data.get('feedback', '')
        appointment.save()
        return Response({'status': 'تم إكمال الموعد'})


# API لحفظ العميل من الشات (بدون تسجيل دخول)
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from apps.agents.models import Agent
import json

@csrf_exempt
def save_lead_from_chat(request, agent_id):
    """حفظ عميل من الشات المضمن"""
    from apps.properties.models import Property
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # Get agent
        agent = Agent.objects.get(id=agent_id)
        
        # Extract phone number
        phone = data.get('phone', '')
        name = data.get('name', '')
        
        if not phone:
            return JsonResponse({'success': False, 'error': 'رقم الجوال مطلوب'}, status=400)
        
        # Check if lead already exists
        existing_lead = Lead.objects.filter(agent=agent, phone=phone).first()
        
        if existing_lead:
            # Update existing lead
            if name and not existing_lead.name:
                existing_lead.name = name
            existing_lead.notes = (existing_lead.notes or '') + f"\n\n--- محادثة جديدة ---\n{data.get('conversation', '')}"
            existing_lead.save()
            lead = existing_lead
        else:
            # Create new lead
            lead = Lead.objects.create(
                agent=agent,
                name=name or 'عميل من الشات',
                phone=phone,
                source='chatbot',
                status='new',
                looking_for=data.get('looking_for', 'buy'),
                city_preference=data.get('city', ''),
                property_type_preference=data.get('interest', ''),
                notes=f"محادثة الشات:\n{data.get('conversation', '')}"
            )
            lead.calculate_score()
            lead.save()
        
        # Add interested properties and update interested_count
        interested_properties = data.get('interested_properties', [])
        if interested_properties:
            for prop_data in interested_properties:
                prop_id = prop_data.get('id')
                if prop_id:
                    try:
                        prop = Property.objects.get(id=prop_id)
                        # Check if not already added
                        if not lead.interested_properties.filter(id=prop.id).exists():
                            lead.interested_properties.add(prop)
                            # Increment interested_count
                            prop.interested_count += 1
                            prop.save(update_fields=['interested_count'])
                    except Property.DoesNotExist:
                        pass
        
        return JsonResponse({
            'success': True, 
            'lead_id': str(lead.id),
            'message': 'تم حفظ بيانات العميل بنجاح'
        })
        
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'الوكيل غير موجود'}, status=404)
    except Exception as e:
        import traceback
        print(f"Save lead error: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
