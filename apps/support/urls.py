# -*- coding: utf-8 -*-
"""
Support URLs - روابط الدعم الفني
"""

from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    # واجهات المستخدم
    path('', views.ticket_list, name='ticket_list'),
    path('create/', views.ticket_create, name='ticket_create'),
    path('ticket/<uuid:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    
    # واجهات الأدمن
    path('admin/', views.admin_ticket_list, name='admin_ticket_list'),
    path('admin/<uuid:ticket_id>/', views.admin_ticket_detail, name='admin_ticket_detail'),
]
