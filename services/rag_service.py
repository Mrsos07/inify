# -*- coding: utf-8 -*-
"""
RAG Service - خدمة استرجاع المعلومات المعززة بالذكاء الاصطناعي
باستخدام Gemini للبحث الذكي في العقارات
"""

import os
import json
import google.generativeai as genai
from typing import List, Dict, Any, Optional
from django.conf import settings


class RAGService:
    """خدمة RAG للبحث الذكي في العقارات"""
    
    def __init__(self):
        # تكوين Gemini
        self.api_key = os.getenv('GEMINI_API_KEY', '')
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None
        
        self.embedding_model = 'models/embedding-001'
    
    def get_property_context(self, agent_id, query: str) -> str:
        """
        استرجاع سياق العقارات المناسبة للاستعلام
        """
        from apps.properties.models import Property
        from apps.agents.models import Agent
        import uuid
        
        properties = None
        
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
                return "لا توجد عقارات متاحة حالياً. يمكنني مساعدتك عندما يتم إضافة عقارات جديدة."
            
            # تحويل العقارات إلى نص للسياق
            properties_context = self._format_properties_for_context(properties)
            
            # إذا كان Gemini متاح، استخدمه للبحث الذكي
            if self.model and self.api_key:
                return self._smart_search(query, properties_context, properties)
            else:
                # بحث بسيط بدون Gemini
                return self._simple_search(query, properties)
                
        except Agent.DoesNotExist:
            return "مرحباً! كيف يمكنني مساعدتك في البحث عن عقار؟"
        except Exception as e:
            print(f"RAG Error: {e}")
            if properties is not None:
                return self._simple_search(query, properties)
            return "مرحباً! أنا نيورا، مساعدك العقاري. كيف يمكنني مساعدتك؟"
    
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
    
    def get_property_details_with_images(self, property_id: int) -> Dict[str, Any]:
        """الحصول على تفاصيل عقار مع صوره"""
        from apps.properties.models import Property
        
        try:
            prop = Property.objects.get(id=property_id)
            images = prop.images.all()
            
            return {
                'id': prop.id,
                'title': prop.title,
                'type': prop.get_property_type_display(),
                'status': prop.get_status_display(),
                'price': prop.price,
                'price_display': f"{prop.price:,.0f} ريال",
                'size': prop.size,
                'bedrooms': prop.bedrooms,
                'bathrooms': prop.bathrooms,
                'city': prop.city,
                'neighborhood': prop.neighborhood,
                'address': prop.address,
                'description': prop.description,
                'images': [
                    {
                        'url': img.image.url if img.image else None,
                        'is_primary': img.is_primary,
                        'caption': img.caption
                    }
                    for img in images
                ],
                'amenities': [a.name for a in prop.amenities.all()],
                'features': {
                    'has_parking': prop.has_parking,
                    'has_pool': prop.has_pool,
                    'has_garden': prop.has_garden,
                    'has_elevator': prop.has_elevator,
                    'is_furnished': prop.is_furnished,
                }
            }
        except Property.DoesNotExist:
            return None
    
    def generate_property_response(self, agent_id, user_message: str) -> Dict[str, Any]:
        """
        توليد رد شامل يتضمن النص والعقارات المقترحة
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
            
            # البحث عن العقارات المناسبة
            context = self.get_property_context(agent_id, user_message)
            
            # استخراج العقارات المقترحة
            suggested_properties = self._extract_matching_properties(user_message, properties)
            
            return {
                'text_response': context,
                'suggested_properties': [
                    self.get_property_details_with_images(p.id) 
                    for p in suggested_properties[:3]
                ],
                'has_properties': len(suggested_properties) > 0
            }
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return {
                'text_response': "عذراً، حدث خطأ. يرجى المحاولة مرة أخرى.",
                'suggested_properties': [],
                'has_properties': False
            }
    
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
