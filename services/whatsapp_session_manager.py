# -*- coding: utf-8 -*-
"""
WhatsApp Session Manager - إدارة جلسات المحادثات بدقة
يحل مشكلة الرد على المحادثة الخاطئة عبر تتبع دقيق للجلسات
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class WhatsAppSessionManager:
    """
    مدير جلسات الواتساب - يضمن الرد على المحادثة الصحيحة
    
    الميزات:
    - تتبع دقيق لكل محادثة بناءً على رقم الهاتف
    - حفظ سياق المحادثة في الذاكرة المؤقتة
    - منع التداخل بين المحادثات المختلفة
    - دعم المحادثات المتزامنة
    """
    
    # مدة انتهاء الجلسة (30 دقيقة)
    SESSION_TIMEOUT = 30 * 60
    
    # مدة قفل المحادثة أثناء المعالجة (30 ثانية)
    PROCESSING_LOCK_TIMEOUT = 30
    
    def __init__(self):
        self.cache_prefix = "whatsapp_session"
        self.lock_prefix = "whatsapp_lock"
        self.context_prefix = "whatsapp_context"
    
    def _get_session_key(self, instance_name: str, phone: str) -> str:
        """توليد مفتاح الجلسة الفريد"""
        return f"{self.cache_prefix}:{instance_name}:{phone}"
    
    def _get_lock_key(self, instance_name: str, phone: str) -> str:
        """توليد مفتاح القفل"""
        return f"{self.lock_prefix}:{instance_name}:{phone}"
    
    def _get_context_key(self, instance_name: str, phone: str) -> str:
        """توليد مفتاح السياق"""
        return f"{self.context_prefix}:{instance_name}:{phone}"
    
    def create_or_get_session(self, instance_name: str, phone: str, 
                              sender_name: str = '') -> Dict[str, Any]:
        """
        إنشاء أو الحصول على جلسة محادثة
        
        Returns:
            dict: معلومات الجلسة
        """
        session_key = self._get_session_key(instance_name, phone)
        session = cache.get(session_key)
        
        if not session:
            # إنشاء جلسة جديدة
            session = {
                'instance_name': instance_name,
                'phone': phone,
                'sender_name': sender_name,
                'conversation_id': None,
                'created_at': timezone.now().isoformat(),
                'last_activity': timezone.now().isoformat(),
                'message_count': 0,
                'is_active': True,
                'metadata': {}
            }
            cache.set(session_key, session, self.SESSION_TIMEOUT)
            logger.info(f"✅ Created new WhatsApp session: {phone}")
        else:
            # تحديث النشاط
            session['last_activity'] = timezone.now().isoformat()
            session['message_count'] += 1
            if sender_name and not session.get('sender_name'):
                session['sender_name'] = sender_name
            cache.set(session_key, session, self.SESSION_TIMEOUT)
            logger.info(f"♻️ Updated WhatsApp session: {phone} (msg #{session['message_count']})")
        
        return session
    
    def get_session(self, instance_name: str, phone: str) -> Optional[Dict[str, Any]]:
        """الحصول على جلسة موجودة"""
        session_key = self._get_session_key(instance_name, phone)
        return cache.get(session_key)
    
    def update_session(self, instance_name: str, phone: str, 
                      updates: Dict[str, Any]) -> bool:
        """تحديث معلومات الجلسة"""
        session_key = self._get_session_key(instance_name, phone)
        session = cache.get(session_key)
        
        if not session:
            return False
        
        session.update(updates)
        session['last_activity'] = timezone.now().isoformat()
        cache.set(session_key, session, self.SESSION_TIMEOUT)
        logger.info(f"📝 Updated session for {phone}: {list(updates.keys())}")
        return True
    
    def link_conversation(self, instance_name: str, phone: str, 
                         conversation_id: str) -> bool:
        """ربط الجلسة بمحادثة في قاعدة البيانات"""
        return self.update_session(instance_name, phone, {
            'conversation_id': conversation_id
        })
    
    def acquire_lock(self, instance_name: str, phone: str) -> bool:
        """
        الحصول على قفل للمحادثة لمنع المعالجة المتزامنة
        
        Returns:
            bool: True إذا تم الحصول على القفل
        """
        lock_key = self._get_lock_key(instance_name, phone)
        
        # محاولة الحصول على القفل
        acquired = cache.add(lock_key, True, self.PROCESSING_LOCK_TIMEOUT)
        
        if acquired:
            logger.info(f"🔒 Acquired lock for {phone}")
        else:
            logger.warning(f"⏳ Lock already held for {phone}")
        
        return acquired
    
    def release_lock(self, instance_name: str, phone: str):
        """تحرير قفل المحادثة"""
        lock_key = self._get_lock_key(instance_name, phone)
        cache.delete(lock_key)
        logger.info(f"🔓 Released lock for {phone}")
    
    def save_context(self, instance_name: str, phone: str, 
                    context: Dict[str, Any]):
        """حفظ سياق المحادثة"""
        context_key = self._get_context_key(instance_name, phone)
        cache.set(context_key, context, self.SESSION_TIMEOUT)
        logger.info(f"💾 Saved context for {phone}")
    
    def get_context(self, instance_name: str, phone: str) -> Dict[str, Any]:
        """الحصول على سياق المحادثة"""
        context_key = self._get_context_key(instance_name, phone)
        return cache.get(context_key) or {}
    
    def end_session(self, instance_name: str, phone: str):
        """إنهاء الجلسة"""
        session_key = self._get_session_key(instance_name, phone)
        context_key = self._get_context_key(instance_name, phone)
        lock_key = self._get_lock_key(instance_name, phone)
        
        cache.delete(session_key)
        cache.delete(context_key)
        cache.delete(lock_key)
        logger.info(f"❌ Ended session for {phone}")
    
    def get_active_sessions(self, instance_name: str) -> list:
        """الحصول على جميع الجلسات النشطة لـ instance معين"""
        # ملاحظة: هذه الطريقة تعتمد على نوع الـ cache المستخدم
        # في بيئة الإنتاج، يفضل استخدام Redis مع SCAN
        sessions = []
        pattern = f"{self.cache_prefix}:{instance_name}:*"
        
        try:
            # محاولة استخدام Redis SCAN إذا كان متاحاً
            from django.core.cache.backends.redis import RedisCache
            cache_backend = cache._cache
            
            if isinstance(cache_backend, RedisCache):
                keys = cache_backend.keys(pattern)
                for key in keys:
                    session = cache.get(key)
                    if session and session.get('is_active'):
                        sessions.append(session)
        except Exception as e:
            logger.warning(f"Could not retrieve active sessions: {e}")
        
        return sessions
    
    def get_session_stats(self, instance_name: str, phone: str) -> Dict[str, Any]:
        """الحصول على إحصائيات الجلسة"""
        session = self.get_session(instance_name, phone)
        
        if not session:
            return {
                'exists': False,
                'message': 'No active session'
            }
        
        created_at = datetime.fromisoformat(session['created_at'])
        last_activity = datetime.fromisoformat(session['last_activity'])
        duration = (timezone.now() - created_at).total_seconds()
        idle_time = (timezone.now() - last_activity).total_seconds()
        
        return {
            'exists': True,
            'phone': phone,
            'sender_name': session.get('sender_name', ''),
            'conversation_id': session.get('conversation_id'),
            'message_count': session['message_count'],
            'duration_seconds': duration,
            'idle_seconds': idle_time,
            'is_active': session['is_active'],
            'created_at': session['created_at'],
            'last_activity': session['last_activity']
        }


# Singleton instance
whatsapp_session_manager = WhatsAppSessionManager()
