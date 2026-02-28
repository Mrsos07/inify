# -*- coding: utf-8 -*-
"""
Core URLs
"""

from django.urls import path
from . import views
from . import whatsapp_views
from . import analytics_views

urlpatterns = [
    path('', views.home, name='home'),
    path('estate/', views.estate_home, name='estate-home'),
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
    path('dashboard/api-docs/', views.api_docs_view, name='api-docs'),
    path('dashboard/webhooks/', views.webhooks_view, name='webhooks'),
    path('dashboard/analytics/', views.analytics_view, name='analytics'),
    path('dashboard/analytics/data/', views.analytics_data, name='analytics-data'),
    path('dashboard/analytics/export/excel/', analytics_views.analytics_export_excel, name='analytics-export-excel'),
    path('dashboard/analytics/export/pdf/', analytics_views.analytics_export_pdf, name='analytics-export-pdf'),
    
    # Team Management
    path('dashboard/team/', views.team_view, name='team'),
    path('api/team/add/', views.team_add_member, name='team-add-member'),
    path('api/team/<uuid:member_id>/toggle/', views.team_toggle_member, name='team-toggle-member'),
    path('api/team/<uuid:member_id>/delete/', views.team_delete_member, name='team-delete-member'),
    path('api/team/<uuid:member_id>/update/', views.team_update_member, name='team-update-member'),
    
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
    path('api/admin/expire-subscriptions/', views.admin_expire_subscriptions, name='admin-expire-subscriptions'),
    path('api/admin/api-keys/', views.admin_get_api_keys, name='admin-get-api-keys'),
    path('api/admin/api-keys/create/', views.admin_create_api_key, name='admin-create-api-key'),
    path('api/admin/api-keys/<uuid:key_id>/delete/', views.admin_delete_api_key, name='admin-delete-api-key'),
    path('api/admin/api-keys/<uuid:key_id>/enable/', views.admin_toggle_api_key, {'action': 'enable'}, name='admin-enable-api-key'),
    path('api/admin/api-keys/<uuid:key_id>/disable/', views.admin_toggle_api_key, {'action': 'disable'}, name='admin-disable-api-key'),
    path('api/admin/support-tickets/', views.admin_support_tickets, name='admin-support-tickets'),
    path('api/admin/support-tickets/<uuid:ticket_id>/reply/', views.admin_support_ticket_reply, name='admin-support-ticket-reply'),
    path('api/admin/send-email/', views.admin_send_email, name='admin-send-email'),
    path('api/admin/analytics/', views.admin_analytics, name='admin-analytics'),
    
    # Agent Stats API
    path('api/agent/<uuid:agent_id>/stats/', views.get_agent_stats, name='get-agent-stats'),
    path('api/agent/<uuid:agent_id>/conversation/', views.increment_conversation, name='increment-conversation'),
    
    # Tour API
    path('api/tour/complete/', views.tour_complete_api, name='tour-complete'),

    # Profile API
    path('api/profile/update/', views.profile_update_api, name='profile-update'),
    path('api/profile/change-password/', views.change_password_api, name='change-password'),
    
    # Payment & Subscription
    path('subscription/', views.subscription_page, name='subscription'),
    path('subscription/expired/', views.subscription_expired_view, name='subscription-expired'),
    path('api/subscription/status/', views.subscription_status_api, name='subscription-status'),
    path('api/subscription/start-trial/', views.start_trial_api, name='start-trial'),
    path('api/subscription/subscribe/', views.subscribe_api, name='subscribe'),
    path('payment/success/', views.payment_success_view, name='payment-success'),
    path('payment/failure/', views.payment_failure_view, name='payment-failure'),
    path('webhooks/streampay/', views.streampay_webhook, name='streampay-webhook'),
    
    # WhatsApp Integration API
    path('api/whatsapp/status/', whatsapp_views.whatsapp_status, name='whatsapp-status'),
    path('api/whatsapp/connect/', whatsapp_views.whatsapp_connect, name='whatsapp-connect'),
    path('api/whatsapp/qr/', whatsapp_views.whatsapp_get_qr, name='whatsapp-get-qr'),
    path('api/whatsapp/disconnect/', whatsapp_views.whatsapp_disconnect, name='whatsapp-disconnect'),
    path('api/whatsapp/settings/', whatsapp_views.whatsapp_settings, name='whatsapp-settings'),
    path('api/whatsapp/send/', whatsapp_views.whatsapp_send_message, name='whatsapp-send'),
    path('api/whatsapp/check/', whatsapp_views.whatsapp_check_connection, name='whatsapp-check'),
]
