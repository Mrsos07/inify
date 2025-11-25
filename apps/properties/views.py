# -*- coding: utf-8 -*-
"""
Properties Views - واجهات برمجة العقارات
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend

from .models import Property, PropertyImage, PropertyAmenity
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
