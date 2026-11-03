# -*- coding: utf-8 -*-
"""
Properties External API - واجهة برمجية خارجية للعقارات (للمؤسسات فقط)
Authentication: API Key في الـ header: X-API-Key: <key>
"""

import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.utils import timezone

logger = logging.getLogger(__name__)


def _authenticate(request, scope=None):
    """التحقق من API Key (Header فقط) وإرجاع الـ agent أو None"""
    if 'api_key' in request.GET:
        return None, JsonResponse({
            'error': 'لا يُقبل API key في رابط الطلب. استخدم Header: X-API-Key',
            'code': 'api_key_in_query',
        }, status=401)
    key = request.headers.get('X-API-Key')
    if not key:
        return None, JsonResponse({'error': 'API key مطلوب', 'code': 'missing_api_key'}, status=401)

    from apps.agents.models import APIKey
    from services.rate_limit import hit_rate_limit
    api_key_obj = APIKey.authenticate(key)
    if api_key_obj is None:
        return None, JsonResponse({'error': 'API key غير صالح', 'code': 'invalid_api_key'}, status=401)

    # التحقق من أن الحساب enterprise
    if api_key_obj.agent.subscription_plan not in ('enterprise', 'pro'):
        return None, JsonResponse({'error': 'هذه الميزة متاحة للمؤسسات فقط', 'code': 'plan_required'}, status=403)

    if scope and not api_key_obj.has_scope(scope):
        return None, JsonResponse({'error': 'صلاحية المفتاح لا تسمح بهذه العملية', 'code': 'insufficient_scope'}, status=403)

    if hit_rate_limit('partner_api_key', str(api_key_obj.id), limit=600, window=3600):
        return None, JsonResponse({'error': 'تم تجاوز حد الطلبات', 'code': 'rate_limited'}, status=429)

    api_key_obj.record_use()
    return api_key_obj.agent, None


def _scope_for(request):
    return 'properties:read' if request.method in ('GET', 'HEAD', 'OPTIONS') else 'properties:write'


def _property_to_dict(prop, include_images=True):
    """تحويل عقار إلى dict للـ API"""
    data = {
        'id': str(prop.id),
        'reference_number': prop.reference_number,
        'title': prop.title,
        'description': prop.description,
        'property_type': prop.property_type,
        'status': prop.status,
        'city': prop.city,
        'area': prop.area,
        'neighborhood': prop.neighborhood,
        'street': prop.street,
        'address': prop.address,
        'latitude': float(prop.latitude) if prop.latitude else None,
        'longitude': float(prop.longitude) if prop.longitude else None,
        'price': float(prop.price),
        'price_per_sqm': float(prop.price_per_sqm) if prop.price_per_sqm else None,
        'rent_period': prop.rent_period,
        'is_negotiable': prop.is_negotiable,
        'size': float(prop.size),
        'bedrooms': prop.bedrooms,
        'bathrooms': prop.bathrooms,
        'living_rooms': prop.living_rooms,
        'floors': prop.floors,
        'floor_number': prop.floor_number,
        'parking_spaces': prop.parking_spaces,
        'furnishing': prop.furnishing,
        'year_built': prop.year_built,
        'is_featured': prop.is_featured,
        'is_active': prop.is_active,
        'views_count': prop.views_count,
        'interested_count': prop.interested_count,
        'created_at': prop.created_at.isoformat(),
        'updated_at': prop.updated_at.isoformat(),
        'amenities': list(prop.amenities.values_list('amenity', flat=True)),
    }
    if include_images:
        data['images'] = [
            {'id': str(img.id), 'url': img.image.url if img.image else None, 'is_primary': img.is_primary}
            for img in prop.images.all()
        ]
    return data


@csrf_exempt
def api_properties_list(request):
    """
    GET  /api/v1/ext/properties/       - قائمة العقارات
    POST /api/v1/ext/properties/       - إضافة عقار جديد
    """
    agent, err = _authenticate(request, _scope_for(request))
    if err:
        return err

    from apps.properties.models import Property

    if request.method == 'GET':
        qs = Property.objects.filter(agent=agent).prefetch_related('amenities', 'images')

        # فلاتر اختيارية
        status = request.GET.get('status')
        property_type = request.GET.get('type')
        city = request.GET.get('city')
        is_active = request.GET.get('is_active')
        try:
            page = max(1, int(request.GET.get('page', 1)))
            per_page = max(1, min(int(request.GET.get('per_page', 20)), 100))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'page/per_page يجب أن تكون أرقاماً', 'code': 'invalid_pagination'}, status=400)

        if status:
            qs = qs.filter(status=status)
        if property_type:
            qs = qs.filter(property_type=property_type)
        if city:
            qs = qs.filter(city__icontains=city)
        if is_active is not None:
            qs = qs.filter(is_active=(is_active.lower() == 'true'))

        total = qs.count()
        offset = (page - 1) * per_page
        properties = qs[offset:offset + per_page]

        return JsonResponse({
            'success': True,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'properties': [_property_to_dict(p) for p in properties],
        })

    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON غير صالح', 'code': 'invalid_json'}, status=400)

        if not isinstance(body, dict):
            return JsonResponse({'error': 'JSON غير صالح', 'code': 'invalid_json'}, status=400)

        required = ['title', 'property_type', 'status', 'city', 'price', 'size']
        missing = [f for f in required if not body.get(f)]
        if missing:
            return JsonResponse({'error': f'حقول مطلوبة: {", ".join(missing)}', 'code': 'missing_fields'}, status=400)

        # Idempotency: نفس المفتاح يعيد نفس النتيجة بدل إنشاء عقار مكرر
        idem_key = (request.headers.get('Idempotency-Key') or '').strip()[:100]
        if idem_key:
            from django.core.cache import cache
            cache_key = f'idem:ext_properties:{agent.id}:{idem_key}'
            existing_id = cache.get(cache_key)
            if existing_id:
                existing = Property.objects.filter(id=existing_id, agent=agent).first()
                if existing:
                    return JsonResponse({'success': True, 'idempotent_replay': True,
                                         'property': _property_to_dict(existing)}, status=200)

        try:
            prop = Property.objects.create(
                agent=agent,
                title=body['title'],
                description=body.get('description', ''),
                property_type=body['property_type'],
                status=body['status'],
                city=body['city'],
                area=body.get('area', ''),
                neighborhood=body.get('neighborhood', ''),
                street=body.get('street', ''),
                address=body.get('address', ''),
                price=body['price'],
                price_per_sqm=body.get('price_per_sqm'),
                rent_period=body.get('rent_period', 'yearly'),
                is_negotiable=body.get('is_negotiable', True),
                size=body['size'],
                bedrooms=body.get('bedrooms', 0),
                bathrooms=body.get('bathrooms', 0),
                living_rooms=body.get('living_rooms', 0),
                floors=body.get('floors', 1),
                floor_number=body.get('floor_number'),
                parking_spaces=body.get('parking_spaces', 0),
                furnishing=body.get('furnishing', 'unfurnished'),
                year_built=body.get('year_built'),
                is_featured=body.get('is_featured', False),
                is_active=body.get('is_active', True),
                owner_notes=body.get('owner_notes', ''),
                agent_notes=body.get('agent_notes', ''),
            )

            # إضافة المميزات
            if body.get('amenities'):
                from apps.properties.models import PropertyAmenity
                for amenity in body['amenities']:
                    PropertyAmenity.objects.create(property=prop, amenity=amenity)

            if idem_key:
                cache.set(cache_key, str(prop.id), 24 * 3600)

            return JsonResponse({
                'success': True,
                'message': 'تم إضافة العقار بنجاح',
                'property': _property_to_dict(prop),
            }, status=201)

        except Exception:
            logger.exception("API create property error")
            return JsonResponse({'error': 'تعذر إنشاء العقار. تحقق من صحة الحقول.', 'code': 'server_error'}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def api_property_detail(request, property_id):
    """
    GET    /api/v1/ext/properties/<id>/  - تفاصيل عقار
    PUT    /api/v1/ext/properties/<id>/  - تعديل عقار
    DELETE /api/v1/ext/properties/<id>/  - حذف عقار
    """
    agent, err = _authenticate(request, _scope_for(request))
    if err:
        return err

    from apps.properties.models import Property
    try:
        prop = Property.objects.prefetch_related('amenities', 'images').get(id=property_id, agent=agent)
    except Property.DoesNotExist:
        return JsonResponse({'error': 'العقار غير موجود', 'code': 'not_found'}, status=404)

    if request.method == 'GET':
        return JsonResponse({'success': True, 'property': _property_to_dict(prop)})

    elif request.method in ('PUT', 'PATCH'):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON غير صالح', 'code': 'invalid_json'}, status=400)
        if not isinstance(body, dict):
            return JsonResponse({'error': 'JSON غير صالح', 'code': 'invalid_json'}, status=400)

        updatable = [
            'title', 'description', 'property_type', 'status', 'city', 'area',
            'neighborhood', 'street', 'address', 'price', 'price_per_sqm',
            'rent_period', 'is_negotiable', 'size', 'bedrooms', 'bathrooms',
            'living_rooms', 'floors', 'floor_number', 'parking_spaces',
            'furnishing', 'year_built', 'is_featured', 'is_active',
            'owner_notes', 'agent_notes', 'latitude', 'longitude',
        ]
        for field in updatable:
            if field in body:
                setattr(prop, field, body[field])
        prop.save()

        if 'amenities' in body:
            from apps.properties.models import PropertyAmenity
            prop.amenities.all().delete()
            for amenity in body['amenities']:
                PropertyAmenity.objects.create(property=prop, amenity=amenity)

        return JsonResponse({'success': True, 'message': 'تم التحديث بنجاح', 'property': _property_to_dict(prop)})

    elif request.method == 'DELETE':
        prop.delete()
        return JsonResponse({'success': True, 'message': 'تم حذف العقار بنجاح'})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


def api_keys_manage(request):
    """
    GET  /api/v1/ext/keys/   - قائمة مفاتيح API
    POST /api/v1/ext/keys/   - إنشاء مفتاح جديد
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'يجب تسجيل الدخول', 'code': 'auth_required'}, status=401)

    try:
        agent = request.user.agent_profile
    except Exception:
        return JsonResponse({'error': 'لا يوجد حساب مسوق', 'code': 'no_agent'}, status=403)

    if agent.subscription_plan not in ('enterprise', 'pro'):
        return JsonResponse({'error': 'هذه الميزة متاحة للمؤسسات فقط', 'code': 'plan_required'}, status=403)

    from apps.agents.models import APIKey

    if request.method == 'GET':
        keys = APIKey.objects.filter(agent=agent)
        return JsonResponse({
            'success': True,
            'keys': [
                {
                    'id': str(k.id),
                    'name': k.name,
                    'key_preview': k.preview,
                    'scopes': k.scopes or list(APIKey.ALL_SCOPES),
                    'is_active': k.is_active,
                    'requests_count': k.requests_count,
                    'last_used': k.last_used.isoformat() if k.last_used else None,
                    'created_at': k.created_at.isoformat(),
                }
                for k in keys
            ]
        })

    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON غير صالح'}, status=400)

        name = body.get('name', '').strip()
        if not name:
            return JsonResponse({'error': 'اسم المفتاح مطلوب', 'code': 'missing_name'}, status=400)

        if APIKey.objects.filter(agent=agent).count() >= 5:
            return JsonResponse({'error': 'الحد الأقصى 5 مفاتيح', 'code': 'limit_reached'}, status=400)

        scopes = body.get('scopes')
        if scopes is not None:
            if not isinstance(scopes, list) or not scopes or any(s not in APIKey.ALL_SCOPES for s in scopes):
                return JsonResponse({'error': f'scopes غير صالحة. المتاح: {", ".join(APIKey.ALL_SCOPES)}',
                                     'code': 'invalid_scopes'}, status=400)

        new_key, raw_key = APIKey.create_for_agent(agent, name, scopes)
        return JsonResponse({
            'success': True,
            'message': 'تم إنشاء المفتاح — احفظه الآن، لن يظهر مرة أخرى',
            'key': {
                'id': str(new_key.id),
                'name': new_key.name,
                'key': raw_key,
                'scopes': new_key.scopes,
                'created_at': new_key.created_at.isoformat(),
            }
        }, status=201)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


def api_key_delete(request, key_id):
    """DELETE /api/v1/ext/keys/<id>/  - حذف مفتاح"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'يجب تسجيل الدخول'}, status=401)

    try:
        agent = request.user.agent_profile
    except Exception:
        return JsonResponse({'error': 'لا يوجد حساب مسوق'}, status=403)

    from apps.agents.models import APIKey
    try:
        key = APIKey.objects.get(id=key_id, agent=agent)
        key.delete()
        return JsonResponse({'success': True, 'message': 'تم حذف المفتاح'})
    except APIKey.DoesNotExist:
        return JsonResponse({'error': 'المفتاح غير موجود'}, status=404)
