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

from .models import Property, PropertyImage, PropertyAmenity, PropertyVideo
from .serializers import (
    PropertySerializer, PropertyDetailSerializer,
    PropertyCreateSerializer, PropertyImageSerializer
)
from services.property_service import PropertyService


class PropertyViewSet(viewsets.ModelViewSet):
    """ViewSet للعقارات"""
    
    permission_classes = [IsAuthenticated]
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
        
        property_obj.save()
        
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
            'welcomeMessage': agent.bot_welcome_message or 'مرحباً! 👋 كيف يمكنني مساعدتك اليوم؟',
            'systemPrompt': agent.bot_system_prompt or '',
            'collectLeads': agent.bot_collect_leads,
            'language': agent.bot_language or 'ar',
            'color': agent.bot_color or '#000000',
            'profileImage': agent.profile_image.url if agent.profile_image else None,
        }
        
        return JsonResponse({'success': True, 'properties': data, 'agent': agent_data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e), 'properties': []}, status=500)
