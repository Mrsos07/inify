# Permission Matrix (RBAC)

Tenant = `Agent` (ADR-0002). All tenant data is filtered server-side by `request.user.agent_profile`;
foreign IDs return 404/400 (never the other tenant's data).

| Spec role | Implementation | Enforced in |
|---|---|---|
| `platform_admin` | Django superuser **or** member of group `platform_admin` (legacy env credentials during transition; static `X-Admin-Key` disabled) | `services/admin_auth.py`, `check_admin_access` |
| `tenant_owner` | User that owns the `Agent` (no `TeamMember` row) | tenant-scoped querysets |
| `agent_operator` / `sales` | `TeamMember.role = 'marketer'` | own `Agent` data, write allowed |
| `read_only` | `TeamMember.role = 'viewer'` | `middleware/role_permission_middleware.py` (all writes refused except self-service) |
| inactive member | `TeamMember.is_active = False` | same middleware (all writes refused) |
| anonymous visitor | — | only public endpoints below |

## Endpoint classes

| Endpoint class | Anonymous | Viewer | Marketer / Owner (own tenant) | Other tenant | Platform admin |
|---|---|---|---|---|---|
| Public listing, chat, calendar availability | ✅ (rate-limited) | ✅ | ✅ | ✅ (public data only) | ✅ |
| Public booking / lead capture | ✅ (rate-limited, own-agent properties only) | ✅ | ✅ | — | ✅ |
| Public chat continuation | ✅ only with signed session token | — | — | ❌ | — |
| Dashboard reads (properties, leads, conversations, appointments) | ❌ 401/302 | ✅ | ✅ | ❌ 404 | — |
| Dashboard writes | ❌ | ❌ 403 `role_forbidden` | ✅ (CSRF token required) | ❌ 404/400 | — |
| Own profile / password / support tickets | ❌ | ✅ | ✅ | ❌ | — |
| Property appointments (customer PII) | ❌ 401 | ✅ read | ✅ | ❌ 404 | — |
| WebSocket live WhatsApp | ❌ closed 4401 | ✅ read | ✅ | ❌ closed 4403 | — |
| Partner API (`X-API-Key`) | key scopes `properties:read` / `properties:write`; header only | | | ❌ | |
| Admin APIs `/api/admin/*`, `/api/settings/save/` | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 403 | ✅ (audited) |
| Inbound webhooks (StreamPay, Evolution, n8n) | signature / per-instance token / per-agent secret required | | | | |

Tests: `tests/test_rbac.py`, `tests/test_admin_csrf_bola.py`, `tests/test_appointments_access.py`,
`tests/test_websocket_access.py`, `tests/test_public_chat_session.py`, `tests/test_api_keys.py`.
