# -*- coding: utf-8 -*-
"""
Support Forms - نماذج الدعم الفني
"""

from django import forms
from .models import SupportTicket


class SupportTicketForm(forms.ModelForm):
    """نموذج إنشاء تذكرة دعم"""
    
    class Meta:
        model = SupportTicket
        fields = ['title', 'category', 'priority', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'عنوان المشكلة أو الطلب',
                'required': True,
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'اشرح المشكلة بالتفصيل...',
                'rows': 6,
                'required': True,
            }),
        }


class AdminResponseForm(forms.ModelForm):
    """نموذج رد الإدارة على التذكرة"""
    
    class Meta:
        model = SupportTicket
        fields = ['status', 'admin_response']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'form-select',
            }),
            'admin_response': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'اكتب ردك هنا...',
                'rows': 5,
            }),
        }
