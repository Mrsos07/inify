# -*- coding: utf-8 -*-
"""
Support Ticket Models - نماذج تذاكر الدعم الفني
"""

import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class SupportTicket(models.Model):
    """تذكرة دعم فني"""
    
    STATUS_CHOICES = [
        ('open', 'مفتوحة'),
        ('in_progress', 'قيد المراجعة'),
        ('resolved', 'تم الحل'),
        ('closed', 'مغلقة'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'منخفضة'),
        ('medium', 'متوسطة'),
        ('high', 'عالية'),
        ('urgent', 'عاجلة'),
    ]
    
    CATEGORY_CHOICES = [
        ('bug', 'خطأ تقني'),
        ('feature', 'طلب ميزة'),
        ('question', 'استفسار'),
        ('complaint', 'شكوى'),
        ('other', 'أخرى'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(max_length=20, unique=True, verbose_name='رقم التذكرة')
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='support_tickets',
        verbose_name='المستخدم'
    )
    
    title = models.CharField(max_length=200, verbose_name='العنوان')
    description = models.TextField(verbose_name='وصف المشكلة')
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='bug',
        verbose_name='التصنيف'
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name='الأولوية'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        verbose_name='الحالة'
    )
    
    admin_response = models.TextField(blank=True, null=True, verbose_name='رد الإدارة')
    responded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responded_tickets',
        verbose_name='تم الرد بواسطة'
    )
    responded_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الرد')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    
    class Meta:
        verbose_name = 'تذكرة دعم'
        verbose_name_plural = 'تذاكر الدعم'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.ticket_number} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.ticket_number:
            last_ticket = SupportTicket.objects.order_by('-created_at').first()
            if last_ticket and last_ticket.ticket_number:
                try:
                    last_num = int(last_ticket.ticket_number.replace('TKT-', ''))
                    self.ticket_number = f"TKT-{last_num + 1:05d}"
                except:
                    self.ticket_number = f"TKT-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            else:
                self.ticket_number = "TKT-00001"
        super().save(*args, **kwargs)
    
    def get_status_display_class(self):
        """إرجاع class CSS للحالة"""
        status_classes = {
            'open': 'status-open',
            'in_progress': 'status-progress',
            'resolved': 'status-resolved',
            'closed': 'status-closed',
        }
        return status_classes.get(self.status, '')
    
    def get_priority_display_class(self):
        """إرجاع class CSS للأولوية"""
        priority_classes = {
            'low': 'priority-low',
            'medium': 'priority-medium',
            'high': 'priority-high',
            'urgent': 'priority-urgent',
        }
        return priority_classes.get(self.priority, '')
