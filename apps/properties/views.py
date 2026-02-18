# -*- coding: utf-8 -*-
"""
Properties Views - واجهات برمجة العقارات
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import json

from .models import Property, PropertyImage, PropertyAmenity, PropertyVideo, PropertyViewingSlot, PropertyViewingCalendar
from .serializers import (
    PropertySerializer, PropertyDetailSerializer,
    PropertyCreateSerializer, PropertyImageSerializer
)
from services.property_service import PropertyService
from apps.core.decorators import HasActiveSubscription


class PropertyViewSet(viewsets.ModelViewSet):
    """ViewSet للعقارات"""
    
    permission_classes = [IsAuthenticated, HasActiveSubscription]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['property_type', 'status', 'city', 'neighborhood', 'is_featured']
    search_fields = ['title', 'description', 'city', 'neighborhood', 'address']
    ordering_fields = ['price', 'size', 'created_at', 'views_count']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """الحصول على عقارات المسوق الحالي فقط"""
        if hasattr(self.request.user, 'agent_profile'):
            return Property.objects.filter(
                agent=self.request.user.agent_profile,
                is_active=True
            )
        return Property.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PropertyDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return PropertyCreateSerializer
        return PropertySerializer
    
    def perform_create(self, serializer):
        """إنشاء عقار جديد"""
        serializer.save(agent=self.request.user.agent_profile)
    
    @action(detail=True, methods=['get'])
    def similar(self, request, pk=None):
        """الحصول على عقارات مشابهة"""
        property_obj = self.get_object()
        service = PropertyService(agent=self.request.user.agent_profile)
        result = service.get_similar_properties(str(property_obj.id))
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """إحصائيات العقارات"""
        service = PropertyService(agent=self.request.user.agent_profile)
        result = service.get_property_statistics()
        return Response(result)
    
    @action(detail=False, methods=['post'])
    def search(self, request):
        """بحث متقدم في العقارات"""
        service = PropertyService(agent=self.request.user.agent_profile)
        result = service.search_properties(**request.data)
        return Response(result)
    
    @action(detail=True, methods=['post'])
    def upload_image(self, request, pk=None):
        """رفع صورة للعقار"""
        property_obj = self.get_object()
        
        if 'image' not in request.FILES:
            return Response(
                {'error': 'الصورة مطلوبة'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        image = PropertyImage.objects.create(
            property=property_obj,
            image=request.FILES['image'],
            alt_text=request.data.get('alt_text', ''),
            is_primary=request.data.get('is_primary', False)
        )
        
        return Response(PropertyImageSerializer(image).data)
    
    @action(detail=True, methods=['delete'], url_path='delete_image/(?P<image_id>[^/.]+)')
    def delete_image(self, request, pk=None, image_id=None):
        """حذف صورة من العقار"""
        property_obj = self.get_object()
        
        try:
            image = PropertyImage.objects.get(id=image_id, property=property_obj)
            image.delete()
            return Response({'status': 'deleted'})
        except PropertyImage.DoesNotExist:
            return Response(
                {'error': 'الصورة غير موجودة'},
                status=status.HTTP_404_NOT_FOUND
            )


class PublicPropertyViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet عام للعقارات (للزوار)"""
    
    permission_classes = [AllowAny]
    serializer_class = PropertySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['property_type', 'status', 'city']
    search_fields = ['title', 'city', 'neighborhood']
    
    def get_queryset(self):
        """الحصول على العقارات النشطة فقط"""
        agent_id = self.request.query_params.get('agent_id')
        
        queryset = Property.objects.filter(
            is_active=True,
            status__in=['for_sale', 'for_rent']
        )
        
        if agent_id:
            queryset = queryset.filter(agent_id=agent_id)
        
        return queryset
    
    def retrieve(self, request, *args, **kwargs):
        """عرض تفاصيل العقار مع زيادة عداد المشاهدات"""
        instance = self.get_object()
        instance.views_count += 1
        instance.save(update_fields=['views_count'])
        
        serializer = PropertyDetailSerializer(instance)
        return Response(serializer.data)


# ============ API Views for Dashboard ============

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@login_required
def save_property(request):
    """حفظ أو تحديث عقار"""
    print(f"=== save_property called ===")
    print(f"Method: {request.method}")
    print(f"User: {request.user}")
    print(f"Is authenticated: {request.user.is_authenticated}")
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        agent = request.user.agent_profile
        print(f"Agent found: {agent}")
    except Exception as e:
        print(f"Agent error: {e}")
        return JsonResponse({'success': False, 'error': 'لا يوجد حساب مسوق'}, status=400)
    
    try:
        property_id = request.POST.get('property_id')
        
        # إنشاء أو تحديث العقار
        if property_id and property_id.strip():
            try:
                property_obj = Property.objects.get(id=property_id, agent=agent)
            except Property.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'العقار غير موجود'}, status=404)
        else:
            property_obj = Property(agent=agent)
        
        # Safe conversion functions
        def safe_int(val, default=0):
            if val is None or val == '':
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default
        
        def safe_float(val, default=0):
            if val is None or val == '':
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default
        
        # تحديث البيانات
        property_obj.title = request.POST.get('title', '')
        property_obj.property_type = request.POST.get('type') or request.POST.get('property_type', 'apartment')
        
        # Handle status/listing_type
        listing_type = request.POST.get('listing_type', 'sale')
        status = request.POST.get('status', '')
        if status in ['for_sale', 'for_rent', 'reserved', 'sold', 'rented']:
            property_obj.status = status
        elif listing_type == 'rent':
            property_obj.status = 'for_rent'
        else:
            property_obj.status = 'for_sale'
        
        property_obj.price = safe_float(request.POST.get('price'))
        property_obj.size = safe_float(request.POST.get('area') or request.POST.get('size'))
        property_obj.city = request.POST.get('city', '')
        property_obj.neighborhood = request.POST.get('district') or request.POST.get('neighborhood', '')
        property_obj.description = request.POST.get('description', '')
        property_obj.bedrooms = safe_int(request.POST.get('bedrooms'))
        property_obj.bathrooms = safe_int(request.POST.get('bathrooms'))
        property_obj.living_rooms = safe_int(request.POST.get('living_rooms'))
        property_obj.floors = safe_int(request.POST.get('floors'), 1)
        property_obj.floor_number = safe_int(request.POST.get('floor') or request.POST.get('floor_number'), None)
        property_obj.parking_spaces = safe_int(request.POST.get('parking_spaces'))
        property_obj.furnishing = request.POST.get('furnishing', 'unfurnished')
        property_obj.year_built = safe_int(request.POST.get('year_built'), None)
        property_obj.address = request.POST.get('address', '')
        property_obj.is_featured = request.POST.get('is_featured') == 'on'
        property_obj.is_negotiable = request.POST.get('is_negotiable') == 'on'
        
        # رابط الموقع (Google Maps)
        location_url = request.POST.get('location_url', '')
        if location_url:
            # استخراج الإحداثيات من رابط Google Maps إذا أمكن
            import re
            coords_match = re.search(r'@(-?\d+\.?\d*),(-?\d+\.?\d*)', location_url)
            if coords_match:
                property_obj.latitude = float(coords_match.group(1))
                property_obj.longitude = float(coords_match.group(2))
        
        # نوع السعر وعدد الدفعات للإيجار
        if property_obj.status == 'for_rent':
            price_type = request.POST.get('price_type', 'yearly')
            property_obj.rent_period = price_type
        
        property_obj.save()
        
        # ═══════════════════════════════════════════════════════════
        # حفظ المميزات والخدمات (Amenities)
        # ═══════════════════════════════════════════════════════════
        amenities = request.POST.getlist('amenities')
        print(f"Amenities received: {amenities}")
        
        # حذف المميزات القديمة وإضافة الجديدة
        property_obj.amenities.all().delete()
        for amenity_code in amenities:
            if amenity_code:
                PropertyAmenity.objects.create(
                    property=property_obj,
                    amenity=amenity_code
                )
        print(f"Amenities saved: {property_obj.amenities.count()}")
        
        # رفع الصور
        images = request.FILES.getlist('images')
        for i, image in enumerate(images):
            PropertyImage.objects.create(
                property=property_obj,
                image=image,
                is_primary=(i == 0 and not property_obj.images.filter(is_primary=True).exists()),
                order=property_obj.images.count()
            )
        
        # رفع الفيديوهات
        videos = request.FILES.getlist('videos')
        for video in videos:
            PropertyVideo.objects.create(
                property=property_obj,
                video=video,
                order=property_obj.videos.count()
            )
        
        return JsonResponse({'success': True, 'property_id': str(property_obj.id)})
    
    except Exception as e:
        import traceback
        print(f"Save property error: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def get_property(request, property_id):
    """الحصول على بيانات عقار"""
    try:
        agent = request.user.agent_profile
        property_obj = Property.objects.get(id=property_id, agent=agent)
        
        data = {
            'id': str(property_obj.id),
            'title': property_obj.title,
            'property_type': property_obj.property_type,
            'status': property_obj.status,
            'price': float(property_obj.price),
            'size': float(property_obj.size),
            'city': property_obj.city,
            'neighborhood': property_obj.neighborhood,
            'description': property_obj.description,
            'bedrooms': property_obj.bedrooms,
            'bathrooms': property_obj.bathrooms,
            'living_rooms': property_obj.living_rooms,
            'floors': property_obj.floors,
            'floor_number': property_obj.floor_number,
            'parking_spaces': property_obj.parking_spaces,
            'furnishing': property_obj.furnishing,
            'year_built': property_obj.year_built,
            'address': property_obj.address,
            'is_featured': property_obj.is_featured,
            'is_negotiable': property_obj.is_negotiable,
            'images': [
                {
                    'id': str(img.id),
                    'url': img.image.url,
                    'is_primary': img.is_primary
                }
                for img in property_obj.images.all()
            ],
            'videos': [
                {
                    'id': str(vid.id),
                    'url': vid.video.url,
                    'title': vid.title
                }
                for vid in property_obj.videos.all()
            ]
        }
        
        return JsonResponse({'success': True, 'property': data})
    except Property.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'العقار غير موجود'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@login_required
def delete_property(request, property_id):
    """حذف عقار"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        agent = request.user.agent_profile
        property_obj = Property.objects.get(id=property_id, agent=agent)
        property_obj.delete()
        return JsonResponse({'success': True})
    except Property.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'العقار غير موجود'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@login_required
def delete_property_image(request, image_id):
    """حذف صورة عقار"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        agent = request.user.agent_profile
        image = PropertyImage.objects.get(id=image_id, property__agent=agent)
        image.delete()
        return JsonResponse({'success': True})
    except PropertyImage.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'الصورة غير موجودة'}, status=404)


@csrf_exempt
@login_required
def delete_property_video(request, video_id):
    """حذف فيديو عقار"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        agent = request.user.agent_profile
        video = PropertyVideo.objects.get(id=video_id, property__agent=agent)
        video.delete()
        return JsonResponse({'success': True})
    except PropertyVideo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'الفيديو غير موجود'}, status=404)


def list_properties(request):
    """الحصول على جميع عقارات المستخدم"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'غير مسجل الدخول', 'properties': []})
    
    try:
        agent = request.user.agent_profile
        properties = Property.objects.filter(agent=agent, is_active=True).order_by('-created_at')
        
        data = []
        for prop in properties:
            primary_image = prop.images.filter(is_primary=True).first()
            if not primary_image:
                primary_image = prop.images.first()
            
            # حساب عدد المعاينات
            viewing_count = prop.viewing_appointments.filter(
                status__in=['pending', 'confirmed']
            ).count()
            
            data.append({
                'id': str(prop.id),
                'reference_number': prop.reference_number,
                'title': prop.title,
                'type': prop.property_type,
                'typeLabel': prop.get_property_type_display(),
                'listing_type': 'sale' if prop.status == 'for_sale' else 'rent',
                'status': prop.status,
                'statusLabel': prop.get_status_display(),
                'price': float(prop.price),
                'area': float(prop.size),
                'city': prop.city,
                'cityLabel': prop.city,
                'district': prop.neighborhood,
                'address': prop.address,
                'description': prop.description,
                'bedrooms': prop.bedrooms,
                'bathrooms': prop.bathrooms,
                'mainImage': primary_image.image.url if primary_image else None,
                'images': [img.image.url for img in prop.images.all()],
                'createdAt': prop.created_at.isoformat(),
                'views_count': prop.views_count,
                'interested_count': prop.interested_count,
                'viewing_count': viewing_count,
            })
        
        return JsonResponse({'success': True, 'properties': data, 'count': len(data)})
    except AttributeError:
        # No agent profile
        return JsonResponse({'success': True, 'properties': [], 'count': 0, 'message': 'لا يوجد حساب وكيل'})
    except Exception as e:
        import traceback
        print(f"list_properties error: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e), 'properties': []}, status=500)


@csrf_exempt
@login_required  
def save_property_json(request):
    """حفظ عقار من JSON"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        agent = request.user.agent_profile
        data = json.loads(request.body)
        
        property_id = data.get('id')
        
        # إنشاء أو تحديث العقار
        if property_id:
            try:
                property_obj = Property.objects.get(id=property_id, agent=agent)
            except Property.DoesNotExist:
                property_obj = Property(agent=agent)
        else:
            property_obj = Property(agent=agent)
        
        # تحديث البيانات
        property_obj.title = data.get('title', '')
        property_obj.property_type = data.get('type', 'apartment')
        
        listing_type = data.get('listing_type', 'sale')
        if listing_type == 'sale':
            property_obj.status = 'for_sale'
        else:
            property_obj.status = 'for_rent'
        
        # تحديث الحالة إذا تم تحديدها
        status_val = data.get('status')
        if status_val:
            if status_val == 'available':
                property_obj.status = 'for_sale' if listing_type == 'sale' else 'for_rent'
            elif status_val == 'reserved':
                property_obj.status = 'reserved'
            elif status_val == 'sold':
                property_obj.status = 'sold' if listing_type == 'sale' else 'rented'
        
        property_obj.price = float(data.get('price') or 0)
        property_obj.size = float(data.get('area') or 0)
        property_obj.city = data.get('city', '')
        property_obj.neighborhood = data.get('district', '')
        property_obj.address = data.get('address', '')
        property_obj.description = data.get('description', '')
        
        # Safe integer conversion
        def safe_int(val, default=0):
            if val is None or val == '':
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default
        
        property_obj.bedrooms = safe_int(data.get('bedrooms'))
        property_obj.bathrooms = safe_int(data.get('bathrooms'))
        property_obj.year_built = safe_int(data.get('year_built'), None)
        property_obj.floor_number = safe_int(data.get('floor'), None)
        
        property_obj.save()
        
        return JsonResponse({'success': True, 'property_id': str(property_obj.id)})
    
    except Exception as e:
        import traceback
        print(f"Save property JSON error: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def get_agent_properties(request, agent_id):
    """الحصول على عقارات وكيل معين (للشات)"""
    try:
        from apps.agents.models import Agent
        agent = Agent.objects.get(id=agent_id)
        properties = Property.objects.filter(agent=agent, is_active=True).order_by('-created_at')
        
        data = []
        for prop in properties:
            primary_image = prop.images.filter(is_primary=True).first()
            if not primary_image:
                primary_image = prop.images.first()
            
            data.append({
                'id': str(prop.id),
                'reference_number': prop.reference_number,
                'title': prop.title,
                'type': prop.property_type,
                'typeLabel': prop.get_property_type_display(),
                'listing_type': 'sale' if prop.status == 'for_sale' else 'rent',
                'status': prop.status,
                'statusLabel': prop.get_status_display(),
                'price': float(prop.price),
                'price_display': prop.get_price_display(),
                'rent_period': prop.rent_period if prop.status == 'for_rent' else None,
                'rent_period_display': prop.get_rent_period_display() if prop.status == 'for_rent' else None,
                'area': float(prop.size),
                'city': prop.city,
                'cityLabel': prop.city,
                'district': prop.neighborhood,
                'address': prop.address,
                'description': prop.description,
                'bedrooms': prop.bedrooms,
                'bathrooms': prop.bathrooms,
                'living_rooms': prop.living_rooms,
                'floor_number': prop.floor_number,
                'furnishing': prop.get_furnishing_display() if prop.furnishing else None,
                'is_negotiable': prop.is_negotiable,
                'mainImage': primary_image.image.url if primary_image else None,
                'images': [img.image.url for img in prop.images.all()],
                'amenities': [a.get_amenity_display() for a in prop.amenities.all()],
            })
        
        # إضافة بيانات الوكيل الكاملة
        agent_data = {
            'id': str(agent.id),
            'name': agent.bot_name or agent.user.get_full_name() or 'Inify',
            'title': agent.bot_title or 'مساعدك العقاري الذكي',
            'personality': agent.bot_personality or '',
            'company': agent.company_name or '',
            'city': agent.city or '',
            'phone': agent.phone or '',
            'email': agent.email or '',
            'welcomeMessage': agent.bot_welcome_message or f"أهلاً وسهلاً! 👋 معك {agent.bot_name or 'المساعد'} من {agent.company_name or 'فريقنا'}. كيف أقدر أساعدك اليوم؟",
            'systemPrompt': agent.bot_system_prompt or '',
            'collectLeads': agent.bot_collect_leads,
            'language': agent.bot_language or 'ar',
            'color': agent.bot_color or '#000000',
            'profileImage': agent.profile_image.url if agent.profile_image else None,
            # إعدادات السياق الإضافية
            'pricingPolicy': getattr(agent, 'bot_pricing_policy', '') or '',
            'viewingPolicy': getattr(agent, 'bot_viewing_policy', '') or '',
            'workAreas': getattr(agent, 'bot_work_areas', '') or '',
            'services': getattr(agent, 'bot_services', '') or '',
            'contactInfo': getattr(agent, 'bot_contact_info', '') or '',
        }
        
        return JsonResponse({'success': True, 'properties': data, 'agent': agent_data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e), 'properties': []}, status=500)


# ═══════════════════════════════════════════════════════════════════════════════
# تقويم المعاينة APIs
# ═══════════════════════════════════════════════════════════════════════════════

@csrf_exempt
def get_property_viewing_calendar(request, property_id):
    """
    الحصول على تقويم المعاينة لعقار معين
    GET /api/properties/<property_id>/viewing-calendar/
    """
    try:
        from datetime import datetime, timedelta
        from apps.leads.models import ViewingAppointment
        
        property_obj = Property.objects.get(id=property_id)
        
        # الحصول على فترات المعاينة المتاحة
        viewing_slots = PropertyViewingSlot.objects.filter(
            property=property_obj,
            is_active=True
        )
        
        # الحصول على الأيام الـ 14 القادمة
        today = datetime.now().date()
        calendar_data = []
        
        for i in range(14):
            date = today + timedelta(days=i)
            day_of_week = date.weekday()
            
            # التحقق من وجود تقويم مخصص لهذا اليوم
            custom_calendar = PropertyViewingCalendar.objects.filter(
                property=property_obj,
                date=date
            ).first()
            
            if custom_calendar and not custom_calendar.is_available:
                # اليوم غير متاح
                calendar_data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'day_name': ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد'][day_of_week],
                    'is_available': False,
                    'slots': [],
                    'notes': custom_calendar.notes
                })
                continue
            
            # الحصول على فترات هذا اليوم
            day_slots = viewing_slots.filter(day_of_week=day_of_week)
            
            if not day_slots.exists():
                # لا توجد فترات لهذا اليوم
                calendar_data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'day_name': ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد'][day_of_week],
                    'is_available': False,
                    'slots': []
                })
                continue
            
            # جمع جميع الأوقات المتاحة
            all_times = []
            for slot in day_slots:
                times = slot.get_available_times(date)
                all_times.extend(times)
            
            # إزالة التكرارات وترتيب الأوقات
            unique_times = {t['time']: t for t in all_times}
            sorted_times = sorted(unique_times.values(), key=lambda x: x['time'])
            
            has_available = any(t['is_available'] for t in sorted_times)
            
            calendar_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'day_name': ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد'][day_of_week],
                'is_available': has_available,
                'slots': sorted_times
            })
        
        return JsonResponse({
            'success': True,
            'property_id': str(property_id),
            'property_title': property_obj.title,
            'calendar': calendar_data
        })
        
    except Property.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'العقار غير موجود'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def book_property_viewing(request, property_id):
    """
    حجز موعد معاينة لعقار
    POST /api/properties/<property_id>/book-viewing/
    
    Body:
    {
        "client_name": "اسم العميل",
        "client_phone": "رقم الجوال",
        "date": "2024-01-15",
        "time": "16:00",
        "notes": "ملاحظات اختيارية"
    }
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        from datetime import datetime
        from apps.leads.models import Lead, ViewingAppointment, LeadActivity
        
        data = json.loads(request.body)
        
        # التحقق من البيانات المطلوبة
        client_name = data.get('client_name', '').strip()
        client_phone = data.get('client_phone', '').strip()
        date_str = data.get('date', '').strip()
        time_str = data.get('time', '').strip()
        notes = data.get('notes', '').strip()
        
        if not client_phone:
            return JsonResponse({'success': False, 'error': 'رقم الجوال مطلوب'}, status=400)
        if not date_str:
            return JsonResponse({'success': False, 'error': 'التاريخ مطلوب'}, status=400)
        if not time_str:
            return JsonResponse({'success': False, 'error': 'الوقت مطلوب'}, status=400)
        
        # الحصول على العقار
        property_obj = Property.objects.get(id=property_id)
        agent = property_obj.agent
        
        # تحويل التاريخ والوقت
        try:
            scheduled_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            scheduled_time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            return JsonResponse({'success': False, 'error': 'صيغة التاريخ أو الوقت غير صحيحة'}, status=400)
        
        # التحقق من أن التاريخ في المستقبل
        if scheduled_date < datetime.now().date():
            return JsonResponse({'success': False, 'error': 'لا يمكن الحجز في تاريخ ماضي'}, status=400)
        
        # التحقق من توفر الموعد
        existing = ViewingAppointment.objects.filter(
            property=property_obj,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            status__in=['pending', 'confirmed']
        ).exists()
        
        if existing:
            return JsonResponse({'success': False, 'error': 'هذا الموعد محجوز مسبقاً'}, status=400)
        
        # إنشاء أو تحديث العميل
        lead, created = Lead.objects.get_or_create(
            agent=agent,
            phone=client_phone,
            defaults={
                'name': client_name or 'عميل جديد',
                'source': 'chatbot',
                'status': 'new'
            }
        )
        
        if not created and client_name:
            lead.name = client_name
            lead.save()
        
        # إنشاء موعد المعاينة
        appointment = ViewingAppointment.objects.create(
            lead=lead,
            property=property_obj,
            agent=agent,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            status='pending',
            duration_minutes=30,
            notes=notes or f'تم الحجز عبر الشات بوت'
        )
        
        # تسجيل النشاط
        LeadActivity.objects.create(
            lead=lead,
            activity_type='viewing',
            description=f'تم حجز موعد معاينة للعقار: {property_obj.title}',
            metadata={
                'appointment_id': str(appointment.id),
                'property_id': str(property_obj.id),
                'source': 'chatbot_calendar'
            }
        )
        
        # تحديث حالة العميل
        lead.status = 'viewing_scheduled'
        lead.save()
        
        # تنسيق الرد
        day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
        day_name = day_names[scheduled_date.weekday()]
        time_formatted = scheduled_time.strftime('%I:%M %p').replace('AM', 'صباحاً').replace('PM', 'مساءً')
        
        return JsonResponse({
            'success': True,
            'message': f'تم حجز موعد المعاينة بنجاح ✅',
            'appointment': {
                'id': str(appointment.id),
                'property_id': str(property_obj.id),
                'property_title': property_obj.title,
                'lead_id': str(lead.id),
                'client_name': lead.name,
                'client_phone': lead.phone,
                'date': date_str,
                'day_name': day_name,
                'time': time_str,
                'time_formatted': time_formatted,
                'status': 'pending'
            }
        })
        
    except Property.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'العقار غير موجود'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'بيانات غير صالحة'}, status=400)
    except Exception as e:
        import logging
        logging.error(f"Error booking viewing: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@login_required
def manage_viewing_slots(request, property_id):
    """
    إدارة فترات المعاينة لعقار
    GET: الحصول على الفترات الحالية
    POST: إضافة فترة جديدة
    DELETE: حذف فترة
    """
    try:
        property_obj = Property.objects.get(id=property_id)
        
        # التحقق من ملكية العقار
        if hasattr(request.user, 'agent_profile'):
            if property_obj.agent != request.user.agent_profile:
                return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
        else:
            return JsonResponse({'success': False, 'error': 'غير مصرح'}, status=403)
        
        if request.method == 'GET':
            slots = PropertyViewingSlot.objects.filter(property=property_obj)
            slots_data = []
            for slot in slots:
                slots_data.append({
                    'id': str(slot.id),
                    'day_of_week': slot.day_of_week,
                    'day_name': dict(PropertyViewingSlot.DAY_CHOICES).get(slot.day_of_week, ''),
                    'start_time': slot.start_time.strftime('%H:%M'),
                    'end_time': slot.end_time.strftime('%H:%M'),
                    'slot_duration': slot.slot_duration,
                    'is_active': slot.is_active
                })
            return JsonResponse({'success': True, 'slots': slots_data})
        
        elif request.method == 'POST':
            data = json.loads(request.body)
            
            from datetime import datetime
            
            slot = PropertyViewingSlot.objects.create(
                property=property_obj,
                day_of_week=data.get('day_of_week', 0),
                start_time=datetime.strptime(data.get('start_time', '09:00'), '%H:%M').time(),
                end_time=datetime.strptime(data.get('end_time', '18:00'), '%H:%M').time(),
                slot_duration=data.get('slot_duration', 30),
                is_active=data.get('is_active', True)
            )
            
            return JsonResponse({
                'success': True,
                'message': 'تم إضافة فترة المعاينة',
                'slot_id': str(slot.id)
            })
        
        elif request.method == 'DELETE':
            data = json.loads(request.body)
            slot_id = data.get('slot_id')
            
            if slot_id:
                PropertyViewingSlot.objects.filter(id=slot_id, property=property_obj).delete()
                return JsonResponse({'success': True, 'message': 'تم حذف الفترة'})
            
            return JsonResponse({'success': False, 'error': 'معرف الفترة مطلوب'}, status=400)
        
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
        
    except Property.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'العقار غير موجود'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def get_property_appointments(request, property_id):
    """
    الحصول على مواعيد المعاينة لعقار معين
    GET /api/properties/<property_id>/appointments/
    """
    try:
        from apps.leads.models import ViewingAppointment
        
        property_obj = Property.objects.get(id=property_id)
        
        appointments = ViewingAppointment.objects.filter(
            property=property_obj
        ).select_related('lead').order_by('-scheduled_date', '-scheduled_time')
        
        appointments_data = []
        for apt in appointments:
            day_names = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
            day_name = day_names[apt.scheduled_date.weekday()]
            
            appointments_data.append({
                'id': str(apt.id),
                'lead_id': str(apt.lead.id),
                'client_name': apt.lead.name,
                'client_phone': apt.lead.phone,
                'date': apt.scheduled_date.strftime('%Y-%m-%d'),
                'day_name': day_name,
                'time': apt.scheduled_time.strftime('%H:%M'),
                'status': apt.status,
                'status_display': apt.get_status_display(),
                'notes': apt.notes,
                'created_at': apt.created_at.strftime('%Y-%m-%d %H:%M')
            })
        
        return JsonResponse({
            'success': True,
            'property_id': str(property_id),
            'property_title': property_obj.title,
            'appointments': appointments_data,
            'total': len(appointments_data)
        })
        
    except Property.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'العقار غير موجود'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ═══════════════════════════════════════════════════════════
# استيراد العقارات من Excel
# ═══════════════════════════════════════════════════════════

@login_required
def download_excel_template(request):
    """
    تحميل نموذج Excel للعقارات
    GET /api/properties/excel/template/
    """
    from django.http import HttpResponse
    from services.excel_import_service import generate_template
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        output = generate_template()
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="property_template.xlsx"'
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating Excel template: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@csrf_exempt
def import_excel_properties(request):
    """
    استيراد العقارات من ملف Excel
    POST /api/properties/excel/import/
    """
    from services.excel_import_service import parse_excel_file, import_properties
    import logging
    
    logger = logging.getLogger(__name__)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    if 'file' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'الملف مطلوب'}, status=400)
    
    excel_file = request.FILES['file']
    
    # التحقق من نوع الملف
    if not excel_file.name.endswith(('.xlsx', '.xls')):
        return JsonResponse({
            'success': False, 
            'error': 'يجب أن يكون الملف بصيغة Excel (.xlsx أو .xls)'
        }, status=400)
    
    try:
        agent = request.user.agent_profile
    except Exception as e:
        logger.error(f"Error getting agent profile: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'لا يوجد حساب مسوق'}, status=404)
    
    try:
        # قراءة الملف
        properties_data, parse_errors = parse_excel_file(excel_file)
        
        if parse_errors and not properties_data:
            return JsonResponse({
                'success': False,
                'error': 'أخطاء في قراءة الملف',
                'errors': parse_errors
            }, status=400)
        
        # استيراد العقارات
        imported_count, import_errors = import_properties(agent, properties_data)
        
        all_errors = parse_errors + import_errors
        
        return JsonResponse({
            'success': True,
            'imported': imported_count,
            'total_in_file': len(properties_data) + len(parse_errors),
            'errors': all_errors if all_errors else None,
            'message': f'تم استيراد {imported_count} عقار بنجاح' + (f' مع {len(all_errors)} أخطاء' if all_errors else '')
        }, status=200)
    
    except Exception as e:
        logger.error(f"Error importing Excel properties: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'حدث خطأ أثناء استيراد العقارات: {str(e)}'
        }, status=500)
