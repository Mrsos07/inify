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
    path('auth/verify-email/', views.verify_email_view, name='verify-email'),
    path('auth/resend-verification/', views.resend_verification_email, name='resend-verification'),
    path('auth/forgot-password/', views.forgot_password_view, name='forgot-password'),
    path('auth/reset-password/', views.reset_password_view, name='reset-password'),
    path('auth/google/', views.google_auth_callback, name='google-auth'),
    path('login/', views.login_view, name='login-alt'),
    path('register/', views.register_view, name='register-alt'),
    
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/properties/', views.properties_view, name='properties'),
    path('dashboard/leads/', views.leads_view, name='leads'),
    path('dashboard/conversations/', views.conversations_view, name='conversations'),
    path('dashboard/bot-settings/', views.bot_settings_view, name='bot-settings'),
    
    # Pricing
    path('pricing/', views.pricing_view, name='pricing'),
    
    # Legal Pages
    path('terms/', views.terms_view, name='terms'),
    path('privacy/', views.privacy_view, name='privacy'),
    
    # Admin Panel
    path('admin-panel-x7k9m/', views.admin_panel_view, name='admin-panel'),
    
    # Chat
    path('embed/', views.embed_chat_view, name='embed-chat'),
    path('chat/live/', views.live_chat_view, name='live-chat'),
    path('chat/', views.chat_view, name='chat'),
    
    # Other Pages
    path('clients/', views.clients_view, name='clients'),
    path('properties/', views.properties_page_view, name='properties-page'),
    path('profile/', views.profile_view, name='profile'),
    path('settings/', views.settings_view, name='settings'),
    
    # Test
    path('test/add-property/', views.test_add_property, name='test-add-property'),
    
    # Global Settings API
    path('api/settings/', views.get_global_settings, name='get-global-settings'),
    path('api/settings/save/', views.save_global_settings, name='save-global-settings'),
    
    # Admin API
    path('api/admin/login/', views.admin_login, name='admin-login'),
    path('api/admin/users/', views.get_all_users, name='get-all-users'),
    path('api/admin/users/update-plan/', views.update_user_plan, name='update-user-plan'),
    path('api/admin/users/<uuid:user_id>/delete/', views.delete_user, name='delete-user'),
    
    # Agent Stats API
    path('api/agent/<uuid:agent_id>/stats/', views.get_agent_stats, name='get-agent-stats'),
    path('api/agent/<uuid:agent_id>/conversation/', views.increment_conversation, name='increment-conversation'),
]
