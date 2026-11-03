# -*- coding: utf-8 -*-
"""
Server-side role enforcement (RBAC) for team members.

- TeamMember.role == 'viewer'  → read-only: every state-changing request is refused,
  except managing the member's own account (profile / password / logout / support tickets).
- Inactive team members (is_active=False) → refused on every state-changing request.

Owners (Agent accounts without a TeamMember row) and platform admins are unaffected.
See docs/security/permission-matrix.md.
"""

from django.http import JsonResponse

SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}

# Self-service actions that stay allowed for read-only members
SELF_SERVICE_PREFIXES = (
    '/auth/',
    '/accounts/',
    '/api/profile/',
    '/api/tour/',
    '/support/',
)


class RolePermissionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in SAFE_METHODS and request.user.is_authenticated \
                and not request.user.is_superuser:
            membership = self._membership(request.user)
            if membership is not None and not request.path.startswith(SELF_SERVICE_PREFIXES):
                if not membership.is_active:
                    return self._deny('تم إيقاف حسابك في الفريق. تواصل مع مدير المؤسسة.')
                if membership.role == 'viewer':
                    return self._deny('صلاحيتك للعرض فقط ولا تسمح بتنفيذ هذا الإجراء.')
        return self.get_response(request)

    @staticmethod
    def _membership(user):
        from apps.agents.models import TeamMember
        try:
            return user.team_membership
        except TeamMember.DoesNotExist:
            return None
        except AttributeError:
            return None

    @staticmethod
    def _deny(message):
        return JsonResponse({'success': False, 'error': message, 'code': 'role_forbidden'}, status=403)
