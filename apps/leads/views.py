# -*- coding: utf-8 -*-
"""
Leads Views - واجهات برمجة العملاء المحتملين
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import SessionAuthentication
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta, date

from .models import Lead, LeadActivity, ViewingAppointment, PropertyCalendar, CalendarBlockedDate
from .serializers import (
    LeadSerializer, LeadDetailSerializer, LeadCreateSerializer,
    LeadActivitySerializer, ViewingAppointmentSerializer, ViewingAppointmentCreateSerializer,
    PropertyCalendarSerializer, PropertyCalendarUpdateSerializer, CalendarBlockedDateSerializer,
    AIAgentAvailabilityRequestSerializer, AIAgentBookingRequestSerializer
)
from services.lead_service import LeadService
from apps.core.decorators import HasActiveSubscription


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session authentication without CSRF check"""
    def enforce_csrf(self, request):
        return  # Skip CSRF check


class LeadViewSet(viewsets.ModelViewSet):
    """ViewSet للعملاء المحتملين"""
    
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated, HasActiveSubscription]
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
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """تحديث حالة العميل"""
        lead = self.get_object()
        new_status = request.data.get('status')
        
        valid_statuses = ['new', 'interested', 'contacted', 'converted', 'viewing_scheduled', 'won', 'lost', 'on_hold']
        if not new_status or new_status not in valid_statuses:
            return Response({'error': f'حالة غير صالحة. الحالات المتاحة: {", ".join(valid_statuses)}'}, status=400)
        
        old_status = lead.status
        lead.status = new_status
        lead.save(update_fields=['status'])
        
        LeadActivity.objects.create(
            lead=lead,
            activity_type='status_changed',
            description=f'تم تغيير الحالة من {old_status} إلى {new_status}'
        )
        
        return Response({
            'success': True,
            'id': str(lead.id),
            'status': lead.status,
            'status_display': lead.get_status_display()
        })

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
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'scheduled_date', 'property']
    ordering = ['scheduled_date', 'scheduled_time']
    pagination_class = None  # إلغاء الـ pagination للمواعيد
    
    def get_queryset(self):
        """الحصول على مواعيد المسوق الحالي فقط"""
        if hasattr(self.request.user, 'agent_profile'):
            return ViewingAppointment.objects.filter(
                agent=self.request.user.agent_profile
            ).select_related('lead', 'property')
        return ViewingAppointment.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ViewingAppointmentCreateSerializer
        return ViewingAppointmentSerializer
    
    def perform_create(self, serializer):
        """إنشاء موعد معاينة جديد وإرسال تأكيد واتساب للعميل"""
        agent = self.request.user.agent_profile
        appointment = serializer.save(agent=agent)

        # تحويل حالة العميل إلى "تم التواصل" بعد حجز الموعد
        lead = appointment.lead
        if lead and lead.status not in ('contacted', 'qualified', 'negotiating', 'converted', 'won'):
            lead.status = 'contacted'
            lead.save(update_fields=['status'])

        # إرسال رسالة تأكيد واتساب للعميل
        self._send_whatsapp_confirmation(appointment, agent)
    
    def _send_whatsapp_confirmation(self, appointment, agent):
        """إرسال رسالة تأكيد الحجز عبر واتساب للعميل"""
        try:
            # التحقق من وجود ربط واتساب نشط
            whatsapp_instance = agent.whatsapp_instance
            if whatsapp_instance.status != 'connected':
                return
            
            client_phone = appointment.lead.phone
            if not client_phone:
                return
            
            # تنسيق التاريخ والوقت
            from datetime import datetime
            date_obj = appointment.scheduled_date
            time_obj = appointment.scheduled_time
            
            day_names = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
            month_names = {1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل', 5: 'مايو', 6: 'يونيو',
                          7: 'يوليو', 8: 'أغسطس', 9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'}
            
            day_name = day_names.get(date_obj.weekday(), '')
            formatted_date = f"{day_name} {date_obj.day} {month_names.get(date_obj.month, '')} {date_obj.year}"
            formatted_time = time_obj.strftime('%I:%M %p').replace('AM', 'صباحاً').replace('PM', 'مساءً')
            
            # بناء معلومات التواصل
            contact_parts = []
            if agent.company_name:
                contact_parts.append(f"🏢 {agent.company_name}")
            contact_phone = agent.whatsapp or agent.phone
            if contact_phone:
                contact_parts.append(f"📞 {contact_phone}")
            if agent.bot_contact_info:
                contact_parts.append(agent.bot_contact_info)
            
            contact_section = '\n'.join(contact_parts) if contact_parts else ''
            
            # بناء الرسالة
            client_name = appointment.lead.name or 'عزيزي العميل'
            property_title = appointment.property.title if appointment.property else 'العقار'
            
            message = f"""✅ تم تأكيد موعد المعاينة

مرحباً {client_name}،

يسعدنا إبلاغك بأنه تم حجز موعد معاينة العقار بنجاح.

🏠 العقار: {property_title}
📅 التاريخ: {formatted_date}
🕐 الوقت: {formatted_time}

نرجو الحضور في الموعد المحدد. إذا كنت بحاجة إلى تغيير الموعد أو لديك أي استفسار، يرجى التواصل معنا.

{contact_section}

شكراً لثقتك بنا 🙏"""
            
            from services.whatsapp_service import whatsapp_service
            whatsapp_service.send_text_message(
                whatsapp_instance.instance_name,
                client_phone,
                message.strip()
            )
            whatsapp_instance.increment_sent()
        except Exception:
            pass  # لا نوقف الحجز إذا فشل إرسال الواتساب
    
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
        appointment.rating = request.data.get('rating')
        appointment.save()
        return Response({'status': 'تم إكمال الموعد'})
    
    @action(detail=True, methods=['post'])
    def reschedule(self, request, pk=None):
        """إعادة جدولة الموعد"""
        appointment = self.get_object()
        new_date = request.data.get('scheduled_date')
        new_time = request.data.get('scheduled_time')
        
        if not new_date or not new_time:
            return Response(
                {'error': 'التاريخ والوقت الجديدين مطلوبين'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # التحقق من التوفر
        from datetime import datetime as dt
        new_date_obj = dt.strptime(new_date, '%Y-%m-%d').date()
        new_time_obj = dt.strptime(new_time, '%H:%M').time()
        
        availability = ViewingAppointment.check_availability(
            property_id=appointment.property_id,
            date=new_date_obj,
            time=new_time_obj,
            duration_minutes=appointment.duration_minutes,
            exclude_id=appointment.id
        )
        
        if not availability['available']:
            return Response(
                {'error': 'الموعد الجديد متعارض مع موعد آخر', 'conflicts': availability['conflicts']},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        appointment.scheduled_date = new_date_obj
        appointment.scheduled_time = new_time_obj
        appointment.end_time = None  # سيتم حسابه تلقائياً
        appointment.status = 'rescheduled'
        appointment.save()
        
        return Response({
            'status': 'تم إعادة جدولة الموعد',
            'new_date': new_date,
            'new_time': new_time
        })
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """المواعيد القادمة"""
        today = date.today()
        appointments = self.get_queryset().filter(
            scheduled_date__gte=today,
            status__in=['pending', 'confirmed']
        ).order_by('scheduled_date', 'scheduled_time')[:10]
        
        serializer = ViewingAppointmentSerializer(appointments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def calendar_view(self, request):
        """عرض التقويم - جميع المواعيد في فترة معينة"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date:
            start_date = date.today()
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if not end_date:
            end_date = start_date + timedelta(days=30)
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        appointments = self.get_queryset().filter(
            scheduled_date__gte=start_date,
            scheduled_date__lte=end_date
        ).order_by('scheduled_date', 'scheduled_time')
        
        # تجميع المواعيد حسب التاريخ
        calendar_data = {}
        for appt in appointments:
            date_str = str(appt.scheduled_date)
            if date_str not in calendar_data:
                calendar_data[date_str] = []
            calendar_data[date_str].append(ViewingAppointmentSerializer(appt).data)
        
        return Response(calendar_data)


class PropertyCalendarViewSet(viewsets.ModelViewSet):
    """ViewSet لتقويم العقار"""
    
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if hasattr(self.request.user, 'agent_profile'):
            return PropertyCalendar.objects.filter(
                property__agent=self.request.user.agent_profile
            ).select_related('property')
        return PropertyCalendar.objects.none()
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return PropertyCalendarUpdateSerializer
        return PropertyCalendarSerializer
    
    @action(detail=True, methods=['get'])
    def available_slots(self, request, pk=None):
        """الحصول على الفترات المتاحة"""
        calendar = self.get_object()
        date_str = request.query_params.get('date')
        
        if not date_str:
            target_date = date.today()
        else:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # التحقق من يوم العمل
        is_working_day = calendar.is_working_day(target_date)
        
        # التحقق من الحظر
        is_blocked = calendar.blocked_dates.filter(date=target_date, is_partial=False).exists()
        
        if not is_working_day or is_blocked:
            return Response({
                'date': str(target_date),
                'slots': [],
                'is_working_day': is_working_day,
                'is_blocked': is_blocked
            })
        
        slots = calendar.get_available_slots(target_date)
        
        return Response({
            'date': str(target_date),
            'slots': slots,
            'is_working_day': is_working_day,
            'is_blocked': is_blocked
        })
    
    @action(detail=True, methods=['get'])
    def week_availability(self, request, pk=None):
        """الحصول على التوفر لأسبوع كامل"""
        calendar = self.get_object()
        start_date_str = request.query_params.get('start_date')
        
        if not start_date_str:
            start_date = date.today()
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
        week_data = []
        for i in range(7):
            current_date = start_date + timedelta(days=i)
            is_working_day = calendar.is_working_day(current_date)
            is_blocked = calendar.blocked_dates.filter(date=current_date, is_partial=False).exists()
            
            slots = []
            if is_working_day and not is_blocked:
                slots = calendar.get_available_slots(current_date)
            
            week_data.append({
                'date': str(current_date),
                'day_name': ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت'][current_date.weekday()],
                'is_working_day': is_working_day,
                'is_blocked': is_blocked,
                'available_slots_count': len(slots),
                'slots': slots
            })
        
        return Response(week_data)
    
    @action(detail=True, methods=['post'])
    def block_date(self, request, pk=None):
        """حظر تاريخ معين"""
        calendar = self.get_object()
        
        blocked_date = CalendarBlockedDate.objects.create(
            calendar=calendar,
            date=request.data.get('date'),
            reason=request.data.get('reason', 'other'),
            notes=request.data.get('notes', ''),
            is_partial=request.data.get('is_partial', False),
            blocked_start_time=request.data.get('blocked_start_time'),
            blocked_end_time=request.data.get('blocked_end_time')
        )
        
        return Response(CalendarBlockedDateSerializer(blocked_date).data)
    
    @action(detail=True, methods=['delete'], url_path='unblock_date/(?P<date_str>[^/.]+)')
    def unblock_date(self, request, pk=None, date_str=None):
        """إلغاء حظر تاريخ"""
        calendar = self.get_object()
        
        try:
            blocked = calendar.blocked_dates.get(date=date_str)
            blocked.delete()
            return Response({'status': 'تم إلغاء الحظر'})
        except CalendarBlockedDate.DoesNotExist:
            return Response(
                {'error': 'التاريخ غير محظور'},
                status=status.HTTP_404_NOT_FOUND
            )


# ============================================
# API للوكيل الذكي (AI Agent)
# ============================================

class AIAgentCalendarAPI(APIView):
    """API للوكيل الذكي للتحقق من التوفر وحجز المواعيد"""
    
    authentication_classes = []  # بدون authentication
    permission_classes = [AllowAny]  # سيتم التحقق من agent_id
    
    def get(self, request, agent_id):
        """
        التحقق من توفر المواعيد
        
        Query params:
            - property_id: معرف العقار
            - date: التاريخ (YYYY-MM-DD)
            - time: الوقت (اختياري، HH:MM)
        """
        from apps.agents.models import Agent
        from apps.properties.models import Property
        
        try:
            agent = Agent.objects.get(id=agent_id)
        except Agent.DoesNotExist:
            return Response({'error': 'الوكيل غير موجود'}, status=404)
        
        property_id = request.query_params.get('property_id')
        date_str = request.query_params.get('date')
        time_str = request.query_params.get('time')
        
        if not property_id or not date_str:
            return Response(
                {'error': 'property_id و date مطلوبين'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            property_obj = Property.objects.get(id=property_id, agent=agent)
        except Property.DoesNotExist:
            return Response({'error': 'العقار غير موجود'}, status=404)
        
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # الحصول على تقويم العقار أو إنشاء واحد افتراضي
        calendar, created = PropertyCalendar.objects.get_or_create(property=property_obj)
        
        # التحقق من السماح بالحجز من الوكيل الذكي
        if not calendar.allow_ai_booking:
            return Response({
                'available': False,
                'message': 'الحجز التلقائي غير مفعل لهذا العقار',
                'slots': []
            })
        
        # التحقق من يوم العمل والحظر
        is_working_day = calendar.is_working_day(target_date)
        is_blocked = calendar.blocked_dates.filter(date=target_date, is_partial=False).exists()
        
        if not is_working_day:
            return Response({
                'available': False,
                'message': 'هذا اليوم ليس يوم عمل',
                'slots': []
            })
        
        if is_blocked:
            return Response({
                'available': False,
                'message': 'هذا اليوم محظور للحجز',
                'slots': []
            })
        
        # إذا تم تحديد وقت معين، التحقق من توفره
        if time_str:
            target_time = datetime.strptime(time_str, '%H:%M').time()
            availability = ViewingAppointment.check_availability(
                property_id=property_id,
                date=target_date,
                time=target_time,
                duration_minutes=calendar.slot_duration
            )
            
            return Response({
                'available': availability['available'],
                'requested_time': time_str,
                'conflicts': availability['conflicts'] if not availability['available'] else [],
                'message': 'الموعد متاح' if availability['available'] else 'الموعد غير متاح'
            })
        
        # إرجاع جميع الفترات المتاحة
        slots = calendar.get_available_slots(target_date)
        
        return Response({
            'available': len(slots) > 0,
            'date': date_str,
            'slots': slots,
            'slot_duration': calendar.slot_duration,
            'message': f'يوجد {len(slots)} فترة متاحة' if slots else 'لا توجد فترات متاحة'
        })
    
    def post(self, request, agent_id):
        """
        حجز موعد معاينة من الوكيل الذكي
        
        Body:
            - property_id: معرف العقار
            - lead_id: معرف العميل (اختياري)
            - client_name: اسم العميل (إذا لم يكن lead_id)
            - client_phone: رقم الجوال (اختياري)
            - scheduled_date: التاريخ
            - scheduled_time: الوقت
            - notes: ملاحظات (اختياري)
        """
        from apps.agents.models import Agent
        from apps.properties.models import Property
        
        try:
            agent = Agent.objects.get(id=agent_id)
        except Agent.DoesNotExist:
            return Response({'error': 'الوكيل غير موجود'}, status=404)
        
        serializer = AIAgentBookingRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        data = serializer.validated_data
        
        # الحصول على العقار
        try:
            property_obj = Property.objects.get(id=data['property_id'], agent=agent)
        except Property.DoesNotExist:
            return Response({'error': 'العقار غير موجود'}, status=404)
        
        # الحصول على التقويم
        calendar, _ = PropertyCalendar.objects.get_or_create(property=property_obj)
        
        if not calendar.allow_ai_booking:
            return Response({
                'success': False,
                'message': 'الحجز التلقائي غير مفعل لهذا العقار'
            })
        
        # التحقق من التوفر
        availability = ViewingAppointment.check_availability(
            property_id=property_obj.id,
            date=data['scheduled_date'],
            time=data['scheduled_time'],
            duration_minutes=data.get('duration_minutes', calendar.slot_duration)
        )
        
        if not availability['available']:
            return Response({
                'success': False,
                'message': 'الموعد غير متاح',
                'conflicts': availability['conflicts']
            })
        
        # الحصول على العميل أو إنشاء واحد جديد
        lead = None
        if data.get('lead_id'):
            try:
                lead = Lead.objects.get(id=data['lead_id'], agent=agent)
            except Lead.DoesNotExist:
                return Response({'error': 'العميل غير موجود'}, status=404)
        else:
            # حفظ المحادثة في الملاحظات
            conversation_text = request.data.get('conversation', '')
            notes_text = f"محادثة الشات:\n{conversation_text}" if conversation_text else ''
            
            # إنشاء عميل جديد
            lead = Lead.objects.create(
                agent=agent,
                name=data.get('client_name', 'عميل من الوكيل الذكي'),
                phone=data.get('client_phone', ''),
                email=data.get('client_email', ''),
                source='website_chat',
                status='contacted',
                notes=notes_text
            )
            lead.interested_properties.add(property_obj)
        
        # إنشاء الموعد
        appointment = ViewingAppointment.objects.create(
            lead=lead,
            property=property_obj,
            agent=agent,
            scheduled_date=data['scheduled_date'],
            scheduled_time=data['scheduled_time'],
            duration_minutes=data.get('duration_minutes', calendar.slot_duration),
            notes=data.get('notes', ''),
            booked_by='ai_agent',
            status='pending'
        )
        
        # تحديث حالة العميل إلى "تم التواصل" بعد حجز الموعد
        lead.status = 'contacted'
        lead.save()
        
        # إنشاء نشاط
        LeadActivity.objects.create(
            lead=lead,
            activity_type='viewing',
            description=f'تم حجز موعد معاينة للعقار {property_obj.title} بتاريخ {data["scheduled_date"]} الساعة {data["scheduled_time"]}',
            metadata={
                'appointment_id': str(appointment.id),
                'property_id': str(property_obj.id),
                'booked_by': 'ai_agent'
            }
        )
        
        return Response({
            'success': True,
            'appointment_id': str(appointment.id),
            'message': 'تم حجز الموعد بنجاح',
            'appointment_details': {
                'date': str(appointment.scheduled_date),
                'time': str(appointment.scheduled_time),
                'property': property_obj.title,
                'property_address': f"{property_obj.city}, {property_obj.neighborhood}" if property_obj.neighborhood else property_obj.city,
                'lead_name': lead.name,
                'status': 'قيد الانتظار'
            }
        })


# API لحفظ العميل من الشات (بدون تسجيل دخول)
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from apps.agents.models import Agent
import json


def list_leads(request):
    """الحصول على جميع عملاء المستخدم - للداشبورد"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'غير مسجل الدخول', 'leads': []})
    
    try:
        agent = request.user.agent_profile
        # تحسين الأداء باستخدام prefetch_related
        leads = Lead.objects.filter(agent=agent).prefetch_related(
            'interested_properties__images',
            'viewing_appointments__property',
            'conversation__messages'
        ).order_by('-created_at')
        
        data = []
        for lead in leads:
            # العقارات المهتم بها
            interested_props = []
            for prop in lead.interested_properties.all():
                primary_image = prop.images.filter(is_primary=True).first()
                if not primary_image:
                    primary_image = prop.images.first()
                interested_props.append({
                    'id': str(prop.id),
                    'title': prop.title,
                    'price': float(prop.price) if prop.price else None,
                    'city': prop.city,
                    'neighborhood': prop.neighborhood,
                    'mainImage': primary_image.image.url if primary_image else None,
                })
            
            # مواعيد المعاينة
            appointments = []
            for appt in lead.viewing_appointments.all().order_by('-scheduled_date'):
                appointments.append({
                    'id': str(appt.id),
                    'property_title': appt.property.title if appt.property else '',
                    'property_id': str(appt.property.id) if appt.property else '',
                    'scheduled_date': str(appt.scheduled_date),
                    'scheduled_time': str(appt.scheduled_time),
                    'status': appt.status,
                    'status_display': appt.get_status_display(),
                })
            
            # المحادثة
            conversation = []
            if lead.conversation:
                # المحادثة من نموذج Conversation
                for msg in lead.conversation.messages.all().order_by('created_at')[:50]:
                    conversation.append({
                        'role': msg.role,
                        'content': msg.content,
                        'created_at': msg.created_at.isoformat() if msg.created_at else None
                    })
            elif lead.notes and 'محادثة' in lead.notes:
                # المحادثة محفوظة في الملاحظات
                notes_lines = lead.notes.split('\n')
                for line in notes_lines:
                    line = line.strip()
                    if line.startswith('العميل:'):
                        conversation.append({
                            'role': 'user',
                            'content': line.replace('العميل:', '').strip(),
                            'created_at': None
                        })
                    elif line.startswith('الوكيل:'):
                        conversation.append({
                            'role': 'assistant',
                            'content': line.replace('الوكيل:', '').strip(),
                            'created_at': None
                        })
            
            data.append({
                'id': str(lead.id),
                'name': lead.name,
                'phone': lead.phone,
                'email': lead.email,
                'status': lead.status,
                'status_display': lead.get_status_display(),
                'source': lead.source,
                'source_display': lead.get_source_display(),
                'urgency': lead.urgency,
                'looking_for': lead.looking_for,
                'city_preference': lead.city_preference,
                'property_type_preference': lead.property_type_preference,
                'neighborhood_preference': lead.neighborhood_preference,
                'budget_min': float(lead.budget_min) if lead.budget_min else None,
                'budget_max': float(lead.budget_max) if lead.budget_max else None,
                'score': lead.score,
                'notes': lead.notes,
                'created_at': lead.created_at.isoformat(),
                'interested_properties_count': lead.interested_properties.count(),
                'interested_properties': interested_props,
                'viewing_appointments': appointments,
                'conversation': conversation,
            })
        
        return JsonResponse({'success': True, 'leads': data, 'count': len(data)})
    except AttributeError:
        return JsonResponse({'success': True, 'leads': [], 'count': 0, 'message': 'لا يوجد حساب وكيل'})
    except Exception as e:
        import traceback
        print(f"list_leads error: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e), 'leads': []}, status=500)


def leads_stats(request):
    """إحصائيات العملاء الحية - خفيفة وسريعة"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'غير مسجل الدخول'}, status=401)
    try:
        agent = request.user.agent_profile
        leads_qs = Lead.objects.filter(agent=agent)
        from apps.leads.models import ViewingAppointment
        stats = {
            'new': leads_qs.filter(status='new').count(),
            'interested': leads_qs.filter(status='interested').count(),
            'contacted': leads_qs.filter(status='contacted').count(),
            'converted': leads_qs.filter(status='converted').count(),
            'appointments': ViewingAppointment.objects.filter(
                agent=agent, status__in=['pending', 'confirmed']
            ).count(),
            'total': leads_qs.count(),
        }
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


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
                looking_for=data.get('looking_for', ''),
                city_preference=data.get('city', ''),
                property_type_preference=data.get('interest', ''),
                notes=f"محادثة الشات:\n{data.get('conversation', '')}"
            )
            lead.calculate_score()
            lead.save()
            # Webhook: عميل جديد
            try:
                from apps.agents.webhook_service import dispatch_webhook, lead_payload
                dispatch_webhook(agent, 'lead.created', lead_payload(lead))
            except Exception:
                pass
        
        # Add interested properties and update interested_count
        interested_properties = data.get('interested_properties', [])
        if interested_properties:
            added_any = False
            for prop_data in interested_properties:
                prop_id = prop_data.get('id')
                if prop_id:
                    try:
                        prop = Property.objects.get(id=prop_id)
                        if not lead.interested_properties.filter(id=prop.id).exists():
                            lead.interested_properties.add(prop)
                            prop.interested_count += 1
                            prop.save(update_fields=['interested_count'])
                            added_any = True
                    except Property.DoesNotExist:
                        pass
            # تحديث حالة العميل إلى مهتم (إذا لم يكن في حالة أعلى)
            if added_any and lead.status in ('new', 'interested'):
                lead.status = 'interested'
                lead.save(update_fields=['status'])
                # Webhook: عميل مهتم بعقار
                try:
                    from apps.agents.webhook_service import dispatch_webhook, lead_payload
                    dispatch_webhook(agent, 'lead.interested', lead_payload(lead))
                except Exception:
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


@csrf_exempt
def book_viewing_from_chat(request, agent_id):
    """
    حجز موعد معاينة من الشات بوت
    
    POST /api/v1/leads/book-viewing/<agent_id>/
    
    Body:
    {
        "client_name": "أحمد",
        "client_phone": "0555123456",
        "property_id": "uuid" (optional),
        "property_title": "شقة في الصفا" (optional),
        "scheduled_date": "2025-12-11",
        "scheduled_time": "17:00",
        "notes": "ملاحظات" (optional)
    }
    """
    from apps.properties.models import Property
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # Get agent
        agent = Agent.objects.get(id=agent_id)
        
        # Extract data
        client_name = data.get('client_name', 'عميل من الشات')
        client_phone = data.get('client_phone', '')
        property_id = data.get('property_id')
        property_title = data.get('property_title', '')
        scheduled_date = data.get('scheduled_date')
        scheduled_time = data.get('scheduled_time', '17:00')
        notes = data.get('notes', '')
        
        # Validation
        if not client_phone:
            return JsonResponse({'success': False, 'error': 'رقم الجوال مطلوب'}, status=400)
        
        if not scheduled_date:
            # Default to tomorrow
            scheduled_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Get or create lead
        lead, created = Lead.objects.get_or_create(
            agent=agent,
            phone=client_phone,
            defaults={
                'name': client_name,
                'source': 'chatbot',
                'status': 'new'
            }
        )
        
        if not created and client_name and client_name != 'عميل من الشات':
            lead.name = client_name
            lead.save()
        
        # Get property
        property_obj = None
        if property_id:
            try:
                property_obj = Property.objects.get(id=property_id)
            except Property.DoesNotExist:
                pass
        
        # If no property_id but property_title, try to find it
        if not property_obj and property_title:
            property_obj = Property.objects.filter(
                agent=agent, 
                title__icontains=property_title,
                is_active=True
            ).first()
        
        # If still no property, use first available
        if not property_obj:
            property_obj = Property.objects.filter(agent=agent, is_active=True).first()
        
        if not property_obj:
            return JsonResponse({
                'success': False, 
                'error': 'لا يوجد عقارات متاحة للحجز'
            }, status=400)
        
        # Parse date and time
        try:
            date_obj = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
        except:
            date_obj = (datetime.now() + timedelta(days=1)).date()
        
        try:
            time_obj = datetime.strptime(scheduled_time, '%H:%M').time()
        except:
            time_obj = datetime.strptime('17:00', '%H:%M').time()
        
        # Check for conflicts
        existing = ViewingAppointment.objects.filter(
            lead__agent=agent,
            scheduled_date=date_obj,
            scheduled_time=time_obj,
            status__in=['pending', 'confirmed']
        ).exists()
        
        if existing:
            # Suggest alternative time (1 hour later)
            alt_time = (datetime.combine(date_obj, time_obj) + timedelta(hours=1)).time()
            return JsonResponse({
                'success': False,
                'error': 'الموعد محجوز',
                'suggested_time': alt_time.strftime('%H:%M')
            }, status=409)
        
        # Create appointment
        appointment = ViewingAppointment.objects.create(
            lead=lead,
            property=property_obj,
            agent=agent,
            scheduled_date=date_obj,
            scheduled_time=time_obj,
            duration_minutes=30,
            notes=notes or f'تم الحجز عبر الشات بوت',
            status='pending'
        )
        
        # Update lead status
        lead.status = 'viewing_scheduled'
        lead.save()

        # Webhook: حجز موعد معاينة
        try:
            from apps.agents.webhook_service import dispatch_webhook, viewing_payload
            dispatch_webhook(agent, 'viewing.booked', viewing_payload(appointment))
        except Exception:
            pass

        # Create activity
        LeadActivity.objects.create(
            lead=lead,
            activity_type='viewing',
            description=f'تم حجز موعد معاينة للعقار {property_obj.title} بتاريخ {scheduled_date} الساعة {scheduled_time}',
            metadata={
                'appointment_id': str(appointment.id),
                'property_id': str(property_obj.id),
                'booked_by': 'chatbot'
            }
        )
        
        # Format response
        day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
        day_name = day_names[date_obj.weekday()]
        time_str = time_obj.strftime('%I:%M %p').replace('AM', 'صباحاً').replace('PM', 'مساءً')
        
        return JsonResponse({
            'success': True,
            'appointment_id': str(appointment.id),
            'lead_id': str(lead.id),
            'message': 'تم حجز الموعد بنجاح',
            'appointment_details': {
                'date': str(date_obj),
                'day_name': day_name,
                'time': scheduled_time,
                'time_formatted': time_str,
                'property': property_obj.title,
                'property_id': str(property_obj.id),
                'client_name': lead.name,
                'client_phone': lead.phone
            }
        })
        
    except Agent.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'الوكيل غير موجود'}, status=404)
    except Exception as e:
        import traceback
        print(f"Book viewing error: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
