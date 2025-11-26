# -*- coding: utf-8 -*-
"""
Core URLs
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('chat/demo/', views.chat_demo, name='chat-demo'),
    path('health/', views.health_check, name='health-check'),
    
    # Auth
    path('auth/login/', views.login_view, name='login'),
    path('auth/register/', views.register_view, name='register'),
    path('auth/logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/bot-settings/', views.bot_settings_view, name='bot-settings'),
]
