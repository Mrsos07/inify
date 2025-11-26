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

@login_required
def save_property(request):
    """حفظ أو تحديث عقار"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        agent = request.user.agent_profile
    except:
        return JsonResponse({'success': False, 'error': 'لا يوجد حساب مسوق'}, status=400)
    
    property_id = request.POST.get('property_id')
    
    # إنشاء أو تحديث العقار
    if property_id:
        try:
            property_obj = Property.objects.get(id=property_id, agent=agent)
        except Property.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'العقار غير موجود'}, status=404)
    else:
        property_obj = Property(agent=agent)
    
    # تحديث البيانات
    property_obj.title = request.POST.get('title', '')
    property_obj.property_type = request.POST.get('property_type', 'apartment')
    property_obj.status = request.POST.get('status', 'for_sale')
    property_obj.price = float(request.POST.get('price', 0))
    property_obj.size = float(request.POST.get('size', 0))
    property_obj.city = request.POST.get('city', '')
    property_obj.neighborhood = request.POST.get('neighborhood', '')
    property_obj.description = request.POST.get('description', '')
    property_obj.bedrooms = int(request.POST.get('bedrooms', 0))
    property_obj.bathrooms = int(request.POST.get('bathrooms', 0))
    property_obj.living_rooms = int(request.POST.get('living_rooms', 0))
    property_obj.floors = int(request.POST.get('floors', 1))
    property_obj.floor_number = int(request.POST.get('floor_number', 0)) if request.POST.get('floor_number') else None
    property_obj.parking_spaces = int(request.POST.get('parking_spaces', 0))
    property_obj.furnishing = request.POST.get('furnishing', 'unfurnished')
    property_obj.year_built = int(request.POST.get('year_built', 0)) if request.POST.get('year_built') else None
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
