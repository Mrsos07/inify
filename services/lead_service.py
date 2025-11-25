# -*- coding: utf-8 -*-
"""
Lead Service - خدمة العملاء المحتملين
"""

import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class LeadService:
    """خدمة إدارة العملاء المحتملين"""
    
    def __init__(self, agent=None):
        """
        تهيئة الخدمة
        
        Args:
            agent: كائن المسوق العقاري
        """
        self.agent = agent
    
    def create_lead(
        self,
        client_name: str,
        phone: str = None,
        email: str = None,
        interested_properties: List[str] = None,
        budget_min: float = None,
        budget_max: float = None,
        requirements: str = None,
        preferred_contact_time: str = None,
        urgency: str = 'exploring',
        notes: str = None,
        conversation_id: str = None,
        source: str = 'website_chat'
    ) -> Dict[str, Any]:
        """
        إنشاء عميل محتمل جديد
        
        Returns:
            بيانات العميل المحتمل
        """
        from apps.leads.models import Lead, LeadActivity
        from apps.chat.models import Conversation
        from apps.properties.models import Property
        
        try:
            # إنشاء Lead
            lead = Lead(
                agent=self.agent,
                name=client_name,
                phone=phone or '',
                email=email or '',
                source=source,
                urgency=urgency,
                budget_min=budget_min,
                budget_max=budget_max,
                special_requirements=requirements or '',
                preferred_contact_time=preferred_contact_time or '',
                notes=notes or ''
            )
            
            # ربط المحادثة
            if conversation_id:
                try:
                    conversation = Conversation.objects.get(id=conversation_id)
                    lead.conversation = conversation
                except Conversation.DoesNotExist:
                    pass
            
            lead.save()
            
            # إضافة العقارات المهتم بها
            if interested_properties:
                properties = Property.objects.filter(
                    id__in=interested_properties,
                    agent=self.agent
                )
                lead.interested_properties.set(properties)
            
            # حساب التقييم
            lead.calculate_score()
            lead.save()
            
            # تسجيل النشاط
            LeadActivity.objects.create(
                lead=lead,
                activity_type='created',
                description=f'تم إنشاء العميل المحتمل من {source}'
            )
            
            # إرسال إشعار للمسوق
            self._notify_agent_new_lead(lead)
            
            # إرسال للـ webhook إن وجد
            self._send_to_webhook(lead, 'new_lead')
            
            return {
                'success': True,
                'message': 'تم تسجيل بياناتك بنجاح. سيتواصل معك فريقنا قريباً.',
                'lead_id': str(lead.id),
                'lead': self._format_lead(lead)
            }
            
        except Exception as e:
            logger.error(f"Create lead error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def schedule_viewing(
        self,
        property_id: str,
        client_name: str,
        client_phone: str,
        preferred_date: str = None,
        preferred_time: str = None,
        notes: str = None,
        lead_id: str = None
    ) -> Dict[str, Any]:
        """
        جدولة موعد معاينة
        
        Returns:
            بيانات الموعد
        """
        from apps.leads.models import Lead, ViewingAppointment, LeadActivity
        from apps.properties.models import Property
        
        try:
            # الحصول على العقار
            property_obj = Property.objects.get(id=property_id, agent=self.agent)
            
            # الحصول على أو إنشاء Lead
            lead = None
            if lead_id:
                try:
                    lead = Lead.objects.get(id=lead_id, agent=self.agent)
                except Lead.DoesNotExist:
                    pass
            
            if not lead:
                # البحث عن lead موجود بنفس رقم الهاتف
                lead = Lead.objects.filter(
                    agent=self.agent,
                    phone=client_phone
                ).first()
                
                if not lead:
                    # إنشاء lead جديد
                    lead_result = self.create_lead(
                        client_name=client_name,
                        phone=client_phone,
                        interested_properties=[property_id]
                    )
                    if lead_result['success']:
                        lead = Lead.objects.get(id=lead_result['lead_id'])
                    else:
                        return lead_result
            
            # تحديد التاريخ والوقت
            if preferred_date:
                try:
                    scheduled_date = datetime.strptime(preferred_date, '%Y-%m-%d').date()
                except ValueError:
                    scheduled_date = date.today()
            else:
                scheduled_date = date.today()
            
            if preferred_time:
                try:
                    scheduled_time = datetime.strptime(preferred_time, '%H:%M').time()
                except ValueError:
                    scheduled_time = datetime.now().time()
            else:
                scheduled_time = datetime.now().time()
            
            # إنشاء موعد المعاينة
            appointment = ViewingAppointment.objects.create(
                lead=lead,
                property=property_obj,
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                notes=notes or ''
            )
            
            # تحديث حالة Lead
            lead.status = 'viewing_scheduled'
            lead.save()
            
            # تسجيل النشاط
            LeadActivity.objects.create(
                lead=lead,
                activity_type='viewing',
                description=f'تم جدولة معاينة للعقار: {property_obj.title}',
                metadata={
                    'property_id': str(property_id),
                    'date': str(scheduled_date),
                    'time': str(scheduled_time)
                }
            )
            
            # إرسال إشعار
            self._notify_agent_viewing(appointment)
            
            # إرسال للـ webhook
            self._send_to_webhook(appointment, 'viewing_scheduled')
            
            return {
                'success': True,
                'message': f'تم حجز موعد المعاينة بنجاح ليوم {scheduled_date} الساعة {scheduled_time}. سيتم التواصل معك للتأكيد.',
                'appointment': {
                    'id': str(appointment.id),
                    'property': property_obj.title,
                    'date': str(scheduled_date),
                    'time': str(scheduled_time),
                    'status': appointment.get_status_display()
                }
            }
            
        except Property.DoesNotExist:
            return {
                'success': False,
                'error': 'العقار غير موجود'
            }
        except Exception as e:
            logger.error(f"Schedule viewing error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_lead_status(
        self,
        lead_id: str,
        status: str,
        notes: str = None
    ) -> Dict[str, Any]:
        """
        تحديث حالة العميل المحتمل
        
        Returns:
            نتيجة التحديث
        """
        from apps.leads.models import Lead, LeadActivity
        
        try:
            lead = Lead.objects.get(id=lead_id, agent=self.agent)
            old_status = lead.status
            lead.status = status
            
            if notes:
                lead.notes = f"{lead.notes}\n\n{datetime.now()}: {notes}"
            
            lead.save()
            
            # تسجيل النشاط
            LeadActivity.objects.create(
                lead=lead,
                activity_type='status_changed',
                description=f'تم تغيير الحالة من {old_status} إلى {status}',
                metadata={'old_status': old_status, 'new_status': status}
            )
            
            return {
                'success': True,
                'message': 'تم تحديث الحالة بنجاح',
                'lead': self._format_lead(lead)
            }
            
        except Lead.DoesNotExist:
            return {
                'success': False,
                'error': 'العميل المحتمل غير موجود'
            }
        except Exception as e:
            logger.error(f"Update lead status error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_lead_details(self, lead_id: str) -> Dict[str, Any]:
        """
        الحصول على تفاصيل عميل محتمل
        
        Returns:
            تفاصيل العميل
        """
        from apps.leads.models import Lead
        
        try:
            lead = Lead.objects.get(id=lead_id, agent=self.agent)
            return {
                'success': True,
                'lead': self._format_lead(lead, detailed=True)
            }
        except Lead.DoesNotExist:
            return {
                'success': False,
                'error': 'العميل المحتمل غير موجود'
            }
    
    def _format_lead(self, lead, detailed: bool = False) -> Dict:
        """تنسيق بيانات العميل المحتمل"""
        data = {
            'id': str(lead.id),
            'name': lead.name,
            'phone': lead.phone,
            'email': lead.email,
            'status': lead.get_status_display(),
            'status_code': lead.status,
            'source': lead.get_source_display(),
            'urgency': lead.get_urgency_display(),
            'score': lead.score,
            'created_at': lead.created_at.isoformat()
        }
        
        if detailed:
            data.update({
                'looking_for': lead.looking_for,
                'property_type_preference': lead.property_type_preference,
                'city_preference': lead.city_preference,
                'neighborhood_preference': lead.neighborhood_preference,
                'budget_min': float(lead.budget_min) if lead.budget_min else None,
                'budget_max': float(lead.budget_max) if lead.budget_max else None,
                'bedrooms_min': lead.bedrooms_min,
                'bathrooms_min': lead.bathrooms_min,
                'special_requirements': lead.special_requirements,
                'preferred_contact_method': lead.preferred_contact_method,
                'preferred_contact_time': lead.preferred_contact_time,
                'notes': lead.notes,
                'ai_summary': lead.ai_summary,
                'interested_properties': [
                    {
                        'id': str(p.id),
                        'title': p.title,
                        'price': p.get_price_display()
                    }
                    for p in lead.interested_properties.all()
                ],
                'activities': [
                    {
                        'type': a.get_activity_type_display(),
                        'description': a.description,
                        'date': a.created_at.isoformat()
                    }
                    for a in lead.activities.all()[:10]
                ]
            })
        
        return data
    
    def _notify_agent_new_lead(self, lead):
        """إرسال إشعار للمسوق عند وجود عميل جديد"""
        if not self.agent or not self.agent.notify_email:
            return
        
        try:
            subject = f'عميل محتمل جديد: {lead.name}'
            message = f"""
            مرحباً،
            
            لديك عميل محتمل جديد:
            
            الاسم: {lead.name}
            الهاتف: {lead.phone}
            البريد: {lead.email}
            الاستعجال: {lead.get_urgency_display()}
            التقييم: {lead.score}
            
            الميزانية: {lead.budget_min or 'غير محدد'} - {lead.budget_max or 'غير محدد'}
            المتطلبات: {lead.special_requirements or 'لا يوجد'}
            
            يرجى التواصل معه في أقرب وقت.
            
            فريق Newra Estate
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.agent.email],
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Email notification error: {str(e)}")
    
    def _notify_agent_viewing(self, appointment):
        """إرسال إشعار للمسوق عند حجز معاينة"""
        if not self.agent or not self.agent.notify_email:
            return
        
        try:
            subject = f'طلب معاينة جديد: {appointment.property.title}'
            message = f"""
            مرحباً،
            
            لديك طلب معاينة جديد:
            
            العميل: {appointment.lead.name}
            الهاتف: {appointment.lead.phone}
            العقار: {appointment.property.title}
            التاريخ: {appointment.scheduled_date}
            الوقت: {appointment.scheduled_time}
            
            يرجى التأكيد مع العميل.
            
            فريق Newra Estate
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.agent.email],
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Email notification error: {str(e)}")
    
    def _send_to_webhook(self, obj, event_type: str):
        """إرسال البيانات للـ webhook"""
        if not self.agent or not self.agent.webhook_url:
            return
        
        try:
            from apps.leads.models import Lead, ViewingAppointment
            
            if isinstance(obj, Lead):
                data = {
                    'event': event_type,
                    'lead': self._format_lead(obj, detailed=True)
                }
            elif isinstance(obj, ViewingAppointment):
                data = {
                    'event': event_type,
                    'appointment': {
                        'id': str(obj.id),
                        'lead_name': obj.lead.name,
                        'lead_phone': obj.lead.phone,
                        'property_id': str(obj.property.id),
                        'property_title': obj.property.title,
                        'date': str(obj.scheduled_date),
                        'time': str(obj.scheduled_time)
                    }
                }
            else:
                data = {'event': event_type, 'data': str(obj)}
            
            headers = {'Content-Type': 'application/json'}
            if self.agent.webhook_secret:
                headers['X-Webhook-Secret'] = self.agent.webhook_secret
            
            response = requests.post(
                self.agent.webhook_url,
                json=data,
                headers=headers,
                timeout=10
            )
            
            logger.info(f"Webhook sent: {event_type}, status: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
