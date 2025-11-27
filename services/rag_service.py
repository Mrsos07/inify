# -*- coding: utf-8 -*-
"""
RAG Service - خدمة استرجاع المعلومات المعززة بالذكاء الاصطناعي
باستخدام Gemini للبحث الذكي في العقارات
وكيل ذكاء اصطناعي عقاري متكامل
"""

import os
import json
import re
import google.generativeai as genai
from typing import List, Dict, Any, Optional
from django.conf import settings


class RAGService:
    """خدمة RAG للبحث الذكي في العقارات - وكيل ذكاء اصطناعي"""
    
    def __init__(self):
        # تكوين Gemini
        self.api_key = os.getenv('GEMINI_API_KEY', '')
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None
        
        self.embedding_model = 'models/embedding-001'
        
        # كلمات مفتاحية لطلب الصور والفيديوهات
        self.media_keywords = [
            'صور', 'صورة', 'صوره', 'صورها', 'صورته', 'صورتها',
            'فيديو', 'فيديوهات', 'مقطع', 'مقاطع',
            'أرني', 'أريني', 'ارني', 'اريني', 'شوفني', 'وريني', 'ورني',
            'عرض', 'اعرض', 'اعرضها', 'اعرضه',
            'شكل', 'شكله', 'شكلها', 'منظر', 'مناظر',
            'شاهد', 'أشاهد', 'اشاهد', 'مشاهدة', 'شوف', 'اشوف', 'أشوف',
            'وين الصور', 'فين الصور', 'ابي اشوف', 'ابغى اشوف',
            'images', 'photos', 'video', 'show', 'view', 'picture'
        ]
        
        # كلمات مفتاحية لطلب عرض العقارات
        self.property_request_keywords = [
            'عقار', 'عقارات', 'شقة', 'شقق', 'فيلا', 'فلل', 'دوبلكس',
            'أرض', 'اراضي', 'مكتب', 'مكاتب', 'محل', 'محلات',
            'ابحث', 'أبحث', 'ادور', 'أدور', 'دور', 'بحث',
            'عندكم', 'عندك', 'متوفر', 'متاح', 'موجود',
            'للبيع', 'للايجار', 'للإيجار', 'تمليك', 'ايجار', 'إيجار',
            'اشتري', 'أشتري', 'استأجر', 'أستأجر',
            'وش عندكم', 'ايش عندكم', 'شو عندكم',
            'ابغى', 'أبغى', 'ابي', 'أبي', 'اريد', 'أريد',
            'property', 'apartment', 'villa', 'rent', 'buy'
        ]
    
    def get_property_context(self, agent_id, query: str) -> str:
        """
        استرجاع سياق العقارات المناسبة للاستعلام
        يُرجع بيانات العقارات فقط (ليس رداً كاملاً)
        """
        from apps.properties.models import Property
        from apps.agents.models import Agent
        import uuid
        
        try:
            # تحويل agent_id إلى UUID إذا كان string
            if isinstance(agent_id, str):
                try:
                    agent_id = uuid.UUID(agent_id)
                except ValueError:
                    pass
            
            agent = Agent.objects.get(id=agent_id)
            properties = Property.objects.filter(agent=agent, is_active=True)
            
            if not properties.exists():
                return "لا توجد عقارات متاحة حالياً لدى هذا المسوق."
            
            # تحويل العقارات إلى نص للسياق (بيانات فقط)
            return self._format_properties_for_context(properties)
                
        except Agent.DoesNotExist:
            return "لا يوجد مسوق بهذا المعرف."
        except Exception as e:
            print(f"RAG Error: {e}")
            return "حدث خطأ في استرجاع العقارات."
    
    def _format_properties_for_context(self, properties) -> str:
        """تنسيق العقارات كسياق نصي"""
        context_parts = []
        
        for prop in properties[:20]:  # حد أقصى 20 عقار
            images = prop.images.all()
            image_info = f"({images.count()} صور متاحة)" if images.exists() else "(لا توجد صور)"
            
            prop_text = f"""
عقار #{prop.id}:
- العنوان: {prop.title}
- النوع: {prop.get_property_type_display()}
- الحالة: {prop.get_status_display()}
- السعر: {prop.price:,.0f} ريال
- المساحة: {prop.size} م²
- الغرف: {prop.bedrooms} | الحمامات: {prop.bathrooms}
- الموقع: {prop.neighborhood}، {prop.city}
- الوصف: {prop.description[:200] if prop.description else 'لا يوجد وصف'}
- الصور: {image_info}
- المميزات: {', '.join([a.name for a in prop.amenities.all()[:5]]) if prop.amenities.exists() else 'غير محدد'}
"""
            context_parts.append(prop_text)
        
        return "\n---\n".join(context_parts)
    
    def _smart_search(self, query: str, context: str, properties) -> str:
        """بحث ذكي باستخدام Gemini"""
        try:
            prompt = f"""أنت مساعد عقاري ذكي. بناءً على استفسار العميل والعقارات المتاحة، قم بما يلي:

1. حدد العقارات الأكثر ملاءمة للاستفسار
2. قدم ملخصاً واضحاً ومفيداً
3. اذكر تفاصيل العقارات المناسبة (السعر، المساحة، الموقع، عدد الغرف)
4. إذا كانت هناك صور متاحة، أشر إلى ذلك

استفسار العميل: {query}

العقارات المتاحة:
{context}

قدم إجابة مفيدة وموجزة بالعربية. إذا لم تجد عقارات مناسبة، اقترح بدائل من المتاح.
"""
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            print(f"Gemini Error: {e}")
            return self._simple_search(query, properties)
    
    def _simple_search(self, query: str, properties) -> str:
        """بحث بسيط بدون AI"""
        query_lower = query.lower()
        results = []
        
        # كلمات مفتاحية للبحث
        keywords = {
            'شقة': 'apartment',
            'فيلا': 'villa',
            'دوبلكس': 'duplex',
            'أرض': 'land',
            'مكتب': 'office',
            'محل': 'shop',
            'للبيع': 'for_sale',
            'للإيجار': 'for_rent',
            'الرياض': 'الرياض',
            'جدة': 'جدة',
            'مكة': 'مكة',
            'المدينة': 'المدينة',
            'الدمام': 'الدمام',
        }
        
        for prop in properties:
            score = 0
            
            # البحث في العنوان والوصف
            if prop.title and query_lower in prop.title.lower():
                score += 3
            if prop.description and query_lower in prop.description.lower():
                score += 2
            if prop.city and prop.city.lower() in query_lower:
                score += 2
            if prop.neighborhood and prop.neighborhood.lower() in query_lower:
                score += 2
            
            # البحث بالكلمات المفتاحية
            for ar_key, en_key in keywords.items():
                if ar_key in query_lower:
                    if prop.property_type == en_key or prop.status == en_key:
                        score += 3
                    if prop.city and ar_key in prop.city:
                        score += 2
            
            # البحث بالسعر
            if 'رخيص' in query_lower or 'أقل' in query_lower:
                if prop.price < 500000:
                    score += 2
            if 'فاخر' in query_lower or 'راقي' in query_lower:
                if prop.price > 2000000:
                    score += 2
            
            if score > 0:
                results.append((prop, score))
        
        # ترتيب حسب النتيجة
        results.sort(key=lambda x: x[1], reverse=True)
        
        if not results:
            # إرجاع أول 3 عقارات إذا لم يتم العثور على نتائج
            results = [(p, 0) for p in properties[:3]]
        
        return self._format_search_results(results[:5])
    
    def _format_search_results(self, results: List) -> str:
        """تنسيق نتائج البحث"""
        if not results:
            return "لم أجد عقارات مطابقة لطلبك. هل يمكنك توضيح متطلباتك أكثر؟"
        
        response_parts = ["إليك العقارات المتاحة التي قد تناسبك:\n"]
        
        for prop, score in results:
            images = prop.images.all()
            image_text = f"📷 {images.count()} صور متاحة" if images.exists() else ""
            
            prop_info = f"""
🏠 **{prop.title}**
   • النوع: {prop.get_property_type_display()} - {prop.get_status_display()}
   • السعر: {prop.price:,.0f} ريال
   • المساحة: {prop.size} م² | {prop.bedrooms} غرف | {prop.bathrooms} حمامات
   • الموقع: {prop.neighborhood}، {prop.city}
   {image_text}
"""
            response_parts.append(prop_info)
        
        response_parts.append("\nهل تريد معرفة المزيد عن أي عقار؟ أو هل لديك متطلبات محددة؟")
        
        return "\n".join(response_parts)
    
    def get_property_details_with_media(self, property_id) -> Dict[str, Any]:
        """الحصول على تفاصيل عقار مع صوره وفيديوهاته"""
        from apps.properties.models import Property
        import uuid
        
        try:
            # تحويل property_id إلى UUID إذا كان string
            if isinstance(property_id, str):
                try:
                    property_id = uuid.UUID(property_id)
                except ValueError:
                    pass
            
            prop = Property.objects.get(id=property_id)
            images = prop.images.all()
            videos = prop.videos.all()
            
            return {
                'id': str(prop.id),
                'title': prop.title,
                'type': prop.get_property_type_display(),
                'status': prop.get_status_display(),
                'price': float(prop.price),
                'price_display': f"{prop.price:,.0f} ريال",
                'size': float(prop.size),
                'bedrooms': prop.bedrooms,
                'bathrooms': prop.bathrooms,
                'city': prop.city,
                'neighborhood': prop.neighborhood,
                'address': prop.address,
                'description': prop.description,
                'images': [
                    {
                        'id': str(img.id),
                        'url': img.image.url if img.image else None,
                        'is_primary': img.is_primary,
                        'alt_text': img.alt_text
                    }
                    for img in images
                ],
                'videos': [
                    {
                        'id': str(vid.id),
                        'url': vid.video.url if vid.video else None,
                        'title': vid.title,
                        'thumbnail': vid.thumbnail.url if vid.thumbnail else None
                    }
                    for vid in videos
                ],
                'amenities': [a.get_amenity_display() for a in prop.amenities.all()],
            }
        except Property.DoesNotExist:
            return None
    
    def get_property_details_with_images(self, property_id) -> Dict[str, Any]:
        """الحصول على تفاصيل عقار مع صوره (للتوافق مع الكود القديم)"""
        return self.get_property_details_with_media(property_id)
    
    def _wants_media(self, query: str) -> bool:
        """التحقق إذا كان المستخدم يطلب صور أو فيديوهات"""
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in self.media_keywords)
    
    def _wants_properties(self, query: str) -> bool:
        """التحقق إذا كان المستخدم يطلب عرض العقارات"""
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in self.property_request_keywords)
    
    def _extract_property_reference(self, query: str, properties) -> Optional[Any]:
        """استخراج العقار المشار إليه في الاستعلام"""
        query_lower = query.lower()
        
        for prop in properties:
            # البحث بالعنوان
            if prop.title and prop.title.lower() in query_lower:
                return prop
            # البحث بكلمات من العنوان
            if prop.title:
                title_words = prop.title.split()
                matches = sum(1 for word in title_words if len(word) > 3 and word.lower() in query_lower)
                if matches >= 2:
                    return prop
        
        return None
    
    def generate_property_response(self, agent_id, user_message: str) -> Dict[str, Any]:
        """
        توليد رد شامل يتضمن النص والعقارات المقترحة مع الصور والفيديوهات
        """
        from apps.properties.models import Property
        from apps.agents.models import Agent
        import uuid
        
        try:
            # تحويل agent_id إلى UUID إذا كان string
            if isinstance(agent_id, str):
                try:
                    agent_id = uuid.UUID(agent_id)
                except ValueError:
                    pass
            
            agent = Agent.objects.get(id=agent_id)
            properties = Property.objects.filter(agent=agent, is_active=True).prefetch_related('images', 'videos')
            
            # التحقق إذا كان المستخدم يطلب صور أو فيديوهات
            wants_media = self._wants_media(user_message)
            
            # التحقق إذا كان المستخدم يطلب عرض العقارات
            wants_properties = self._wants_properties(user_message)
            
            # البحث عن عقار محدد مشار إليه
            referenced_property = self._extract_property_reference(user_message, properties)
            
            # البحث عن العقارات المناسبة
            context = self.get_property_context(agent_id, user_message)
            
            # استخراج العقارات المقترحة
            suggested_properties = self._extract_matching_properties(user_message, properties)
            
            # إذا كان يطلب صور/فيديو لعقار محدد
            if wants_media and referenced_property:
                property_details = self.get_property_details_with_media(referenced_property.id)
                if property_details:
                    # بناء رد يتضمن معلومات الصور والفيديوهات
                    media_response = self._build_media_response(property_details)
                    return {
                        'text_response': media_response,
                        'suggested_properties': [property_details],
                        'has_properties': True,
                        'show_media': True
                    }
            
            # إذا كان يطلب صور/فيديو بشكل عام
            if wants_media and suggested_properties:
                properties_with_media = []
                for p in suggested_properties[:3]:
                    details = self.get_property_details_with_media(p.id)
                    if details and (details.get('images') or details.get('videos')):
                        properties_with_media.append(details)
                
                if properties_with_media:
                    return {
                        'text_response': "إليك العقارات مع الصور والفيديوهات المتاحة:",
                        'suggested_properties': properties_with_media,
                        'has_properties': True,
                        'show_media': True
                    }
            
            # عرض العقارات فقط إذا طلب العميل ذلك
            if wants_properties or wants_media:
                # إذا لم يتم العثور على عقارات مقترحة، استخدم جميع العقارات
                if not suggested_properties:
                    suggested_properties = list(properties[:3])
                
                # أرسل تفاصيل العقارات مع الصور
                properties_with_details = []
                for p in suggested_properties[:3]:
                    details = self.get_property_details_with_media(p.id)
                    if details:
                        properties_with_details.append(details)
                
                return {
                    'text_response': context,
                    'suggested_properties': properties_with_details,
                    'has_properties': len(properties_with_details) > 0,
                    'show_media': wants_media or any(p.get('images') for p in properties_with_details)
                }
            
            # إذا لم يطلب عقارات، لا ترسل بطاقات
            return {
                'text_response': context,
                'suggested_properties': [],
                'has_properties': False,
                'show_media': False
            }
            
        except Exception as e:
            print(f"Error generating response: {e}")
            import traceback
            traceback.print_exc()
            return {
                'text_response': "عذراً، حدث خطأ. يرجى المحاولة مرة أخرى.",
                'suggested_properties': [],
                'has_properties': False,
                'show_media': False
            }
    
    def _build_media_response(self, property_details: Dict) -> str:
        """بناء رد يتضمن معلومات الصور والفيديوهات"""
        response_parts = [f"إليك تفاصيل عقار: **{property_details['title']}**\n"]
        
        images = property_details.get('images', [])
        videos = property_details.get('videos', [])
        
        if images:
            response_parts.append(f"📷 يتوفر {len(images)} صور للعقار")
        
        if videos:
            response_parts.append(f"🎬 يتوفر {len(videos)} فيديو للعقار")
        
        response_parts.append(f"\n💰 السعر: {property_details.get('price_display', property_details.get('price'))}")
        response_parts.append(f"📐 المساحة: {property_details.get('size')} م²")
        response_parts.append(f"🛏️ الغرف: {property_details.get('bedrooms')} | 🚿 الحمامات: {property_details.get('bathrooms')}")
        response_parts.append(f"📍 الموقع: {property_details.get('neighborhood', '')}, {property_details.get('city', '')}")
        
        if property_details.get('description'):
            response_parts.append(f"\n📝 الوصف: {property_details['description'][:200]}...")
        
        response_parts.append("\n\nيمكنك مشاهدة الصور والفيديوهات أدناه 👇")
        
        return "\n".join(response_parts)
    
    def _extract_matching_properties(self, query: str, properties) -> List:
        """استخراج العقارات المطابقة للاستعلام"""
        query_lower = query.lower()
        matches = []
        
        type_mapping = {
            'شقة': 'apartment', 'شقق': 'apartment',
            'فيلا': 'villa', 'فلل': 'villa',
            'دوبلكس': 'duplex',
            'أرض': 'land', 'أراضي': 'land',
            'مكتب': 'office', 'مكاتب': 'office',
            'محل': 'shop', 'محلات': 'shop',
        }
        
        status_mapping = {
            'للبيع': 'for_sale', 'بيع': 'for_sale', 'شراء': 'for_sale',
            'للإيجار': 'for_rent', 'إيجار': 'for_rent', 'استئجار': 'for_rent',
        }
        
        target_type = None
        target_status = None
        target_city = None
        
        # تحديد النوع المطلوب
        for ar, en in type_mapping.items():
            if ar in query_lower:
                target_type = en
                break
        
        # تحديد الحالة المطلوبة
        for ar, en in status_mapping.items():
            if ar in query_lower:
                target_status = en
                break
        
        # تحديد المدينة
        cities = ['الرياض', 'جدة', 'مكة', 'المدينة', 'الدمام', 'الخبر']
        for city in cities:
            if city in query_lower:
                target_city = city
                break
        
        for prop in properties:
            score = 0
            
            if target_type and prop.property_type == target_type:
                score += 5
            if target_status and prop.status == target_status:
                score += 3
            if target_city and target_city in prop.city:
                score += 3
            
            # البحث في العنوان والوصف
            if prop.title and any(word in prop.title.lower() for word in query_lower.split()):
                score += 2
            
            if score > 0:
                matches.append((prop, score))
        
        # ترتيب وإرجاع
        matches.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matches[:5]]


# Singleton instance
rag_service = RAGService()
