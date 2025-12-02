# -*- coding: utf-8 -*-
"""
Property Service - خدمة العقارات
"""

import logging
from typing import Dict, List, Optional, Any
from decimal import Decimal
from django.db.models import Q

logger = logging.getLogger(__name__)


class PropertyService:
    """خدمة إدارة العقارات"""
    
    def __init__(self, agent=None):
        """
        تهيئة الخدمة
        
        Args:
            agent: كائن المسوق العقاري
        """
        self.agent = agent
    
    def search_properties(
        self,
        property_type: str = 'any',
        status: str = 'any',
        city: str = None,
        neighborhood: str = None,
        min_price: float = None,
        max_price: float = None,
        min_size: float = None,
        max_size: float = None,
        bedrooms: int = None,
        bathrooms: int = None,
        amenities: List[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        البحث في العقارات
        
        Returns:
            نتائج البحث
        """
        from apps.properties.models import Property, PropertyStatus, PropertyType
        
        try:
            # بناء الاستعلام
            queryset = Property.objects.filter(is_active=True)
            
            # تصفية حسب المسوق
            if self.agent:
                queryset = queryset.filter(agent=self.agent)
            
            # نوع العقار
            if property_type and property_type != 'any':
                queryset = queryset.filter(property_type=property_type)
            
            # حالة العرض
            if status and status != 'any':
                queryset = queryset.filter(status=status)
            
            # الموقع
            if city:
                queryset = queryset.filter(
                    Q(city__icontains=city) | Q(area__icontains=city)
                )
            
            if neighborhood:
                queryset = queryset.filter(neighborhood__icontains=neighborhood)
            
            # السعر
            if min_price is not None:
                queryset = queryset.filter(price__gte=Decimal(str(min_price)))
            
            if max_price is not None:
                queryset = queryset.filter(price__lte=Decimal(str(max_price)))
            
            # المساحة
            if min_size is not None:
                queryset = queryset.filter(size__gte=Decimal(str(min_size)))
            
            if max_size is not None:
                queryset = queryset.filter(size__lte=Decimal(str(max_size)))
            
            # الغرف والحمامات
            if bedrooms is not None:
                queryset = queryset.filter(bedrooms__gte=bedrooms)
            
            if bathrooms is not None:
                queryset = queryset.filter(bathrooms__gte=bathrooms)
            
            # المميزات
            if amenities:
                for amenity in amenities:
                    queryset = queryset.filter(amenities__amenity=amenity)
            
            # ترتيب النتائج
            queryset = queryset.order_by('-is_featured', '-created_at')[:limit]
            
            # تحويل النتائج
            properties = []
            for prop in queryset:
                properties.append(self._format_property(prop))
            
            return {
                'success': True,
                'count': len(properties),
                'properties': properties
            }
            
        except Exception as e:
            logger.error(f"Property search error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'properties': []
            }
    
    def get_property_details(self, property_id: str) -> Dict[str, Any]:
        """
        الحصول على تفاصيل عقار محدد
        
        Args:
            property_id: معرف العقار
        
        Returns:
            تفاصيل العقار
        """
        from apps.properties.models import Property
        
        try:
            # بناء الاستعلام
            queryset = Property.objects.filter(id=property_id, is_active=True)
            
            # تصفية حسب المسوق
            if self.agent:
                queryset = queryset.filter(agent=self.agent)
            
            prop = queryset.first()
            
            if not prop:
                return {
                    'success': False,
                    'error': 'العقار غير موجود أو غير متاح'
                }
            
            # زيادة عداد المشاهدات
            prop.views_count += 1
            prop.save(update_fields=['views_count'])
            
            return {
                'success': True,
                'property': self._format_property(prop, detailed=True)
            }
            
        except Exception as e:
            logger.error(f"Property details error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _format_property(self, prop, detailed: bool = False) -> Dict:
        """
        تنسيق بيانات العقار للعرض
        
        Args:
            prop: كائن العقار
            detailed: عرض تفاصيل إضافية
        
        Returns:
            بيانات العقار منسقة
        """
        # البيانات الأساسية
        data = {
            'id': str(prop.id),
            'title': prop.title,
            'type': prop.get_property_type_display(),
            'type_code': prop.property_type,
            'status': prop.get_status_display(),
            'status_code': prop.status,
            'price': float(prop.price),
            'price_display': prop.get_price_display(),
            'rent_period': prop.rent_period if prop.status == 'for_rent' else None,
            'rent_period_display': prop.get_rent_period_display() if prop.status == 'for_rent' else None,
            'is_negotiable': prop.is_negotiable,
            'city': prop.city,
            'area': prop.area,
            'neighborhood': prop.neighborhood,
            'size': float(prop.size),
            'size_display': f"{prop.size} م²",
            'bedrooms': prop.bedrooms,
            'bathrooms': prop.bathrooms,
            'is_featured': prop.is_featured,
        }
        
        # الصورة الرئيسية
        primary_image = prop.images.filter(is_primary=True).first()
        if not primary_image:
            primary_image = prop.images.first()
        
        data['primary_image'] = primary_image.image.url if primary_image else None
        
        # المميزات الرئيسية (أول 3)
        amenities = list(prop.amenities.values_list('amenity', flat=True)[:3])
        data['main_amenities'] = amenities
        
        if detailed:
            # بيانات تفصيلية إضافية
            data.update({
                'description': prop.description,
                'address': prop.address,
                'street': prop.street,
                'living_rooms': prop.living_rooms,
                'floors': prop.floors,
                'floor_number': prop.floor_number,
                'parking_spaces': prop.parking_spaces,
                'furnishing': prop.get_furnishing_display(),
                'year_built': prop.year_built,
                'age_years': prop.age_years,
                'price_per_sqm': float(prop.price_per_sqm) if prop.price_per_sqm else None,
                'owner_notes': prop.owner_notes,
                'created_at': prop.created_at.isoformat(),
                'views_count': prop.views_count,
            })
            
            # جميع المميزات
            all_amenities = []
            for amenity in prop.amenities.all():
                all_amenities.append({
                    'code': amenity.amenity,
                    'name': amenity.get_amenity_display()
                })
            data['amenities'] = all_amenities
            
            # جميع الصور
            images = []
            for img in prop.images.all():
                images.append({
                    'id': str(img.id),
                    'url': img.image.url,
                    'is_primary': img.is_primary,
                    'alt': img.alt_text
                })
            data['images'] = images
            
            # الموقع الجغرافي
            if prop.latitude and prop.longitude:
                data['location'] = {
                    'lat': float(prop.latitude),
                    'lng': float(prop.longitude)
                }
        
        return data
    
    def get_similar_properties(
        self,
        property_id: str,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        الحصول على عقارات مشابهة
        
        Args:
            property_id: معرف العقار الأصلي
            limit: عدد النتائج
        
        Returns:
            العقارات المشابهة
        """
        from apps.properties.models import Property
        
        try:
            # الحصول على العقار الأصلي
            original = Property.objects.get(id=property_id)
            
            # البحث عن عقارات مشابهة
            queryset = Property.objects.filter(
                is_active=True,
                property_type=original.property_type,
                status=original.status,
                city=original.city
            ).exclude(id=property_id)
            
            if self.agent:
                queryset = queryset.filter(agent=self.agent)
            
            # ترتيب حسب قرب السعر
            price_range = original.price * Decimal('0.2')  # 20% نطاق
            queryset = queryset.filter(
                price__gte=original.price - price_range,
                price__lte=original.price + price_range
            ).order_by('price')[:limit]
            
            properties = [self._format_property(p) for p in queryset]
            
            return {
                'success': True,
                'count': len(properties),
                'properties': properties
            }
            
        except Property.DoesNotExist:
            return {
                'success': False,
                'error': 'العقار غير موجود'
            }
        except Exception as e:
            logger.error(f"Similar properties error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_property_statistics(self) -> Dict[str, Any]:
        """
        إحصائيات العقارات
        
        Returns:
            إحصائيات متنوعة
        """
        from apps.properties.models import Property, PropertyStatus, PropertyType
        from django.db.models import Count, Avg, Min, Max
        
        try:
            queryset = Property.objects.filter(is_active=True)
            
            if self.agent:
                queryset = queryset.filter(agent=self.agent)
            
            stats = {
                'total': queryset.count(),
                'for_sale': queryset.filter(status=PropertyStatus.FOR_SALE).count(),
                'for_rent': queryset.filter(status=PropertyStatus.FOR_RENT).count(),
                'by_type': {},
                'by_city': {},
                'price_stats': {}
            }
            
            # إحصائيات حسب النوع
            type_stats = queryset.values('property_type').annotate(count=Count('id'))
            for item in type_stats:
                type_display = dict(PropertyType.choices).get(item['property_type'], item['property_type'])
                stats['by_type'][type_display] = item['count']
            
            # إحصائيات حسب المدينة
            city_stats = queryset.values('city').annotate(count=Count('id')).order_by('-count')[:5]
            for item in city_stats:
                stats['by_city'][item['city']] = item['count']
            
            # إحصائيات الأسعار
            price_agg = queryset.aggregate(
                avg_price=Avg('price'),
                min_price=Min('price'),
                max_price=Max('price')
            )
            stats['price_stats'] = {
                'average': float(price_agg['avg_price']) if price_agg['avg_price'] else 0,
                'minimum': float(price_agg['min_price']) if price_agg['min_price'] else 0,
                'maximum': float(price_agg['max_price']) if price_agg['max_price'] else 0,
            }
            
            return {
                'success': True,
                'statistics': stats
            }
            
        except Exception as e:
            logger.error(f"Statistics error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
