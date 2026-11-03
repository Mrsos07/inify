# Traceability Matrix — Inify V2

- **Baseline:** `main` @ `30a0126` (2026-11-02)
- **Source of findings:** `docs/architecture/current-state-audit.md` (F-xx ids)
- **Status values:** `Not started` · `Planned (awaiting approval)` · `In progress` · `Done (tests: …)` · `Blocked (decision: …)`

## A. Requirement → Gap matrix

| Requirement ID | Current implementation | File:line | Gap | Risk | Proposed change | Test | Status |
|---|---|---|---|---|---|---|---|
| SEC-01a Secrets out of Git/image | Prod env files tracked; not in `.dockerignore`; `COPY . .` | `.gitignore`, `.dockerignore`, `Dockerfile`, `.env.production`, `.env.production.secure` | Real secrets in repo + image + history (F-01) | Critical | `git rm --cached` both files; ignore `.env*` except `*.example`; exclude in `.dockerignore`; add `.env.production.example` with fake values | Image test: build and assert no `.env*` except examples inside `/app` | In progress — `.gitignore` updated + `.env.production` untracked (2026-11-02, staged, not committed); remaining: `.env.production.secure`, `.dockerignore`, example file, image test |
| SEC-01b Secret scanning in CI | None; no CI | — | No guard (F-01) | High | `.github/workflows/security.yml` running Gitleaks on PR/push + `.gitleaks.toml` | CI job green on clean tree; red on seeded fake secret | Planned (awaiting approval) |
| SEC-01c Rotation + history cleanup | Not done | — | Leaked values remain valid | Critical | Written rotation runbook (owner executes); history-rewrite **plan only** (`git filter-repo`), force-push impact documented | Owner checklist | Blocked (decision: owner approval for rotation + force push) |
| SEC-01d Compose literals | Literal DB creds | `docker-compose.evolution.yml:8,35` | Hard-coded credentials (F-01) | Medium | Replace with `${VAR}` refs + example env | `docker compose config` resolves | Planned (awaiting approval) |
| SEC-02a Admin via identity, not static key | `X-Admin-Key` + env username/password; `==` compare | `apps/core/views.py:1450-1520` | No per-admin identity/audit; key leak = full admin (F-09) | High | `check_admin_access` → Django user with `is_superuser` or `platform_admin` group; legacy key behind `ADMIN_LEGACY_KEY_ENABLED` (default off after transition), `hmac.compare_digest`; rate-limit on `REMOTE_ADDR` (trusted-proxy aware) | Allow/deny tests: anon, tenant user, staff, superuser, legacy key on/off | Planned (awaiting approval) |
| SEC-02b RBAC roles + permission matrix | Owner + `TeamMember.role ∈ {marketer, viewer}` | `apps/agents/models.py:973-1012` | No central policy; viewer not enforced on writes | Medium | `apps/core/permissions.py` (tenant resolver + role checks), role mapping per ADR-0002; `docs/security/permission-matrix.md` | Parametrised allow/deny per role per endpoint | Planned (awaiting approval) |
| SEC-02c MFA for admin | None | — | — | Medium | Proposed for P0-late/P1 (django-otp or allauth MFA) | — | Blocked (decision: MFA library) |
| SEC-03a Appointments endpoint protection | Anonymous, returns phone/notes | `apps/properties/views.py:917-962` | PII leak (F-02) | Critical | `login_required` + `property.agent == tenant` else 404; no PII for non-owners | anon→401/302, other tenant→404, owner→200 | Planned (awaiting approval) |
| SEC-03b Public chat session token | `conversation_id` = ownership proof, unscoped lookup | `apps/chat/views.py:795-799` | Hijack (F-03) | Critical | Issue signed token (`django.core.signing`, bound to conversation+agent, TTL); lookup `Conversation(id, agent)`; invalid/absent token → new conversation (backward compatible); widget JS stores token | Token tamper, cross-agent, expiry, legacy client without token | Planned (awaiting approval) |
| SEC-03c WebSocket auth + scope | No auth; unscoped queries; can send WA messages | `apps/chat/consumers.py:21-192` | Cross-tenant read/send (F-04) | Critical | Reject if `scope['user']` anonymous or not owner of `agent_id`; scope all queries by agent | Channels `WebsocketCommunicator` tests: anon, other tenant, owner | Planned (awaiting approval) |
| SEC-03d BOLA in serializers | `lead`/`property` PK from any tenant | `apps/leads/serializers.py:277-308`; `PropertyCalendarSerializer` | Cross-tenant create (F-07) | Critical | Restrict querysets to `request.user.agent_profile` in serializer `__init__`/`validate` | Create with foreign lead/property → 400 | Planned (awaiting approval) |
| SEC-03e Public lead/booking scoping | Unscoped `Property.objects.get(id=...)` | `apps/leads/views.py:936,1035`; `AIAgentCalendarAPI` `:516-735` | Cross-tenant pollution (F-08) | Critical | `Property.objects.get(id=..., agent=agent)`; throttle public endpoints | Foreign property id → ignored/404 | Planned (awaiting approval) |
| SEC-03f Public config leakage | Global/agent system prompts public | `apps/core/views.py:1370-1396`; `apps/properties/views.py:588` | Prompt/policy disclosure (F-10) | High | Admin-only full settings; public subset without prompts; templates `embed.html`/`chat-live.html` updated (server already builds prompts) | Anonymous response lacks `systemPrompt` | Planned (awaiting approval) |
| SEC-03g Tenant-scoped queries for all models | Dashboard querysets mostly scoped | various | Gaps listed above | — | Add cross-tenant regression suite covering Property, Lead, Conversation, Appointment, Agent, TeamMember, Subscription, Webhook, APIKey, TokenUsage | `tests/security/test_cross_tenant.py` | Planned (awaiting approval) |
| SEC-04a Payment webhook integrity | HMAC only if secret set; no replay window/dedup; weak amount check | `apps/core/views.py:2563-2805`; `services/streampay_service.py:317-346` | Fail-open + replay (F-06) | Critical | Fail-closed (500→503 log if secret unset; 401 if bad sig); timestamp tolerance (configurable, default 300s); `InboundWebhookEvent` inbox (unique provider+event_id) — additive migration; require amount + currency `SAR` match; optional fetch of invoice/payment from StreamPay before activation | Forged → 401; missing secret → reject; replay → no second effect; amount/currency mismatch → rejected | Planned (awaiting approval) |
| SEC-04b WhatsApp webhook auth | None (instance name only) | `apps/chat/whatsapp_views.py:34-71` | Forged messages (F-05) | Critical | Per-instance random `webhook_token` (additive field); webhook URL `.../whatsapp/<instance>/<token>/` (or header if Evolution version supports it — to verify); constant-time check; old URL accepted only while `WHATSAPP_WEBHOOK_LEGACY_ALLOWED=True` and re-registration command for existing instances | No/invalid token → 401; valid → processed; legacy flag behaviour | Blocked (decision: auth mechanism + migration window) |
| SEC-04c Dedup / replay | Cache-only 10-min dedup | `apps/chat/whatsapp_views.py:177-186` | Lost on restart / per-process (F-24) | High | Inbox table unique `(provider, external_event_id, tenant)` | Duplicate delivery → single effect | Planned (P0 minimal, P1 full) |
| SEC-04d No raw body logging | Raw body to `webhook_debug.log` + print | `apps/chat/whatsapp_views.py:40-54` | PII in logs (F-15) | High | Remove; log event type + ids only | Log capture asserts no phone/text | Planned (awaiting approval) |
| SEC-04e n8n webhook | Secret optional; `!=` compare | `apps/chat/views.py:622-626` | Unauthenticated AI usage (F-14) | High | Require secret; `compare_digest`; 401 when unset | No secret configured → 401 | Planned (awaiting approval) |
| SEC-05a Remove `csrf_exempt` on session endpoints | 59 uses | see audit F-11 | CSRF exposure | High | Remove from session endpoints in batches; ensure JS sends `X-CSRFToken`; keep only on token/signature-authenticated webhooks & partner API; `ACCOUNT_LOGOUT_ON_GET=False` | Django test client with `enforce_csrf_checks=True`: missing token → 403; with token → 200 | Planned (awaiting approval) |
| SEC-05b CORS/CSRF/cookies/HSTS | Mostly OK in prod | `config/settings.py:23-41,59-67,286-289` | Defaults include `host.docker.internal`, `*.onrender.com` (F-28) | Low | Env-specific allowlists; document | `check --deploy` | Planned |
| SEC-05c API keys header-only + hashed | Query string allowed; plaintext | `apps/properties/api_views.py:20-35`; `apps/agents/models.py:573` | Key leakage (F-13) | High | Header only (query param rejected behind flag); additive `key_hash`, `key_prefix` + data migration backfill; lookup by hash; show once on create; keep plaintext column until removal approved | Query key → 401; hashed lookup works for old & new keys | Planned (awaiting approval) |
| SEC-05d Rate limits | DRF anon/user throttles only for DRF views; plain views unthrottled | `config/settings.py:276-283` | Abuse of public endpoints | High | Cache-backed throttle helper per IP/agent/API key for public chat, booking, lead, calendar endpoints; request size limits (`DATA_UPLOAD_MAX_MEMORY_SIZE`) | 429 after threshold | Planned (awaiting approval) |
| SEC-05e SSRF in outbound webhooks | Any http(s), redirects followed | `apps/agents/webhook_views.py:58,113`; `webhook_service.py:63` | SSRF (F-12) | High | `services/url_safety.py`: https only (http behind flag for dev), DNS resolve + block private/loopback/link-local/metadata/reserved, no redirects, re-check at send time | Unit tests for blocked IP classes, DNS rebinding check at send | Planned (awaiting approval) |
| SEC-05f Error hygiene | `str(e)` returned to clients | e.g. `apps/properties/views.py:914,962`; `apps/leads/views.py:967` | Info leak (F-15) | Medium | Generic messages + server-side `logger.exception` | Forced exception → generic body | Planned (awaiting approval) |
| SEC-05g Debug endpoint | `test/add-property/` live | `apps/core/views.py:1250-1365`, `apps/core/urls.py` | Test code in prod (F-19) | Low | Route only when `DEBUG=True` | Route 404 when `DEBUG=False` | Planned (awaiting approval) |
| SEC-05h Public counter tamper | Anonymous increment | `apps/core/views.py:1981-2003` | F-18 | Low | Throttle + require agent active; or derive from real conversations | 429 / ignored | Planned (awaiting approval) |
| ARC-01 Modular boundaries | 6 apps, fat views (core/views.py 3097 lines) | `apps/*` | Logic in views | Medium | Extract services per domain without moving models (ADR-0001) | Existing + new tests | Not started (P1) |
| ARC-02 Broker + workers | Threads in web workers | `webhook_service.py:128`, `webhook_views.py:170`, `chat/whatsapp_views.py:112`, `core/whatsapp_views.py:528` | Lost work on restart | High | Celery + durable broker (ADR-0004) | Kill worker mid-task → task retried | Blocked (decision: broker) |
| ARC-03 Inbox/Outbox | None | — | No durable events | High | `InboundWebhookEvent` (P0 minimal) + `OutboxEvent` (P1) | Replay/idempotency tests | Not started (P1) |
| ARC-04 Redis channels + ASGI | InMemory; WSGI in Docker | `config/settings.py:142-146`; `Dockerfile` | WS broken in prod (F-17) | High | `channels_redis` when `REDIS_URL`; run Daphne/uvicorn ASGI | 2-instance WS broadcast test | Not started (P1) |
| AI-01 Unified runtime | 3 OpenAI clients, 5 call sites in views | `services/ai_service.py`, `openai_service.py`, `smart_agent_service.py`; `apps/chat/views.py:429,694,744,811,878`; `apps/*/whatsapp_views.py` | Duplicated logic | Medium | `AgentRuntime` + `LLMGateway` behind feature flag | Shadow tests | Not started (P2) |
| AI-02 Orchestrator limits | Ad-hoc per service | `services/smart_agent_service.py:163-215` | No central limits | Medium | max_iterations/deadline/fingerprint | Loop tests | Not started (P2) |
| AI-03 Tool registry + guards | `services/agent_tools.py` | `services/agent_tools.py` | Tenant checks inside tools to verify | High | Typed tool registry with tenant guard | Tool authz tests | Not started (P2) |
| AI-04 Hybrid retrieval | `services/rag_service.py`, `property_service.py` | — | No FTS/pgvector | Medium | Structured filters → FTS → vector | Retrieval tests | Not started (P2) |
| AI-05 Metering | `TokenUsage.log` in 3 of 8 call sites | `services/ai_service.py:149`; `openai_service.py:218,257` | Unmetered: `ai_service.py:214,366,403`; `smart_agent_service.py:163,215` (F-22) | Medium | Meter in `LLMGateway` | Every call logged | Not started (P2) |
| DOM-01 Booking integrity | `exists()` then `create()` | `apps/properties/views.py:752-787`; `apps/leads/views.py:1069-1095,656-705` | Race (F-16) | High | `transaction.atomic` + `select_for_update` on property; partial unique constraint `(property, date, time)` for active statuses after duplicate report | Concurrent booking test (PostgreSQL) | Not started (P3) |
| DOM-02 Lead dedup | Lookups on encrypted phone never match | `apps/leads/models.py:65-67` + call sites in audit F-29 | Duplicate leads (F-29) | High | Additive `phone_hash` (HMAC) + backfill + lookups by hash; unique `(agent, phone_hash)` after dedup report | Same phone twice → one lead | Not started (P3, candidate to pull into P0 — decision) |
| DOM-03 Billing entitlements | Plan checks scattered | `middleware/subscription_middleware.py`; `apps/core/decorators.py` | No entitlement model | Medium | Explicit entitlements + quotas | Billing lifecycle tests | Not started (P3) |
| INT-01 Partner API | API key + JSON views | `apps/properties/api_views.py` | No OpenAPI/scopes/idempotency | Medium | DRF + OpenAPI + scopes | Contract tests | Not started (P4) |
| OPS-01 Observability | Text logs; file handler w/o encoding | `config/settings.py:315-344` | No structured logs/redaction (F-27) | Medium | JSON logs + redaction filter + request_id | Log redaction tests | Not started (P4; encoding fix candidate for P0) |
| OPS-02 CI/CD & images | No CI; root container; single stage | `Dockerfile`, `requirements.txt` | F-25, F-26 | Medium | Multi-stage non-root image, pinned deps, CI pipeline | CI green | Not started (P4; minimal CI in P0) |

## B. Endpoint inventory (owner app · auth · data)

| Route | Handler | App | Auth today | Data | Notes / finding |
|---|---|---|---|---|---|
| `health/` | `config.urls.health_check` | config | none | none | — |
| `admin/` | Django admin | django | staff session | all | — |
| `accounts/*` | allauth | allauth | — | identity | F-20 |
| `auth/login/`, `auth/register/`, `login/`, `register/` | `core.views.login_view/register_view` | core | none (csrf_exempt) | identity | F-11 |
| `auth/forgot-password/`, `auth/reset-password/`, `auth/resend-verification/`, `auth/google/` | core | core | none (csrf_exempt) | identity | F-11 |
| `dashboard/*` pages | core | core | session | tenant | — |
| `dashboard/analytics/data/`, `/export/*` | core / analytics_views | core | session | tenant | to verify scoping in tests |
| `api/team/*` | core | core | session (csrf_exempt) | tenant | F-11 |
| `api/profile/update/`, `api/profile/change-password/` | core | core | session (csrf_exempt) | identity | F-11 |
| `api/tour/complete/` | core | core | session (csrf_exempt) | tenant | F-11 |
| `api/settings/` | `get_global_settings` | core | **none** | global prompt | F-10 |
| `api/settings/save/` | `save_global_settings` | core | admin key/session (csrf_exempt) | global config + OpenAI key | F-09 |
| `api/admin/*` (login, users, plans, delete, expire, api-keys, tickets, email, analytics) | core | core | admin key/session (csrf_exempt) | platform | F-09, F-11 |
| `api/agent/<id>/stats/` | `get_agent_stats` | core | session + owner check | tenant | OK (non-agent users bypass check — to test) |
| `api/agent/<id>/conversation/` | `increment_conversation` | core | **none** | counter | F-18 |
| `api/subscription/*` | core | core | session (csrf_exempt on writes) | billing | F-11 |
| `payment/success/`, `payment/failure/` | core | core | session | billing | — |
| `webhooks/streampay/` | `streampay_webhook` | core | HMAC (fail-open) | billing | F-06 |
| `api/whatsapp/*` | core.whatsapp_views | core | session (csrf_exempt on writes) | tenant channel | F-11 |
| `embed/`, `chat/live/`, `chat/`, `chat/demo/` | core pages | core | mixed | public | F-10 |
| `test/add-property/` | `test_add_property` | core | session | tenant | F-19 |
| `api/v1/properties/list/` (ViewSet) | `PropertyViewSet` | properties | session/token | tenant | scoped |
| `api/v1/properties/public/`, `public/<id>/` | `PublicPropertyViewSet` | properties | none | public listings | OK (active only) |
| `api/v1/properties/save/`, `save-json/`, `detail/<id>/delete/`, `images/<id>/delete/`, `videos/<id>/delete/`, `excel/import/` | properties.views | properties | session (csrf_exempt) | tenant | F-11 |
| `api/v1/properties/my/`, `detail/<id>/`, `excel/template/` | properties.views | properties | session | tenant | — |
| `api/v1/properties/agent/<agent_id>/` | `get_agent_properties` | properties | **none** | listings + agent config | F-10 |
| `api/v1/properties/<id>/viewing-calendar/` | properties.views | properties | none | availability | public by design |
| `api/v1/properties/<id>/book-viewing/` | `book_property_viewing` | properties | **none** (csrf_exempt) | creates lead+appointment | F-16, SEC-05d |
| `api/v1/properties/<id>/viewing-slots/` | `manage_viewing_slots` | properties | session + owner | tenant | — |
| `api/v1/properties/<id>/appointments/` | `get_property_appointments` | properties | **none** | **customer PII** | F-02 |
| `api/v1/properties/ext/properties/`, `ext/properties/<id>/` | api_views | properties | API key (header/query) | tenant | F-13 |
| `api/v1/properties/ext/keys/`, `ext/keys/<id>/delete/` | api_views | properties | to verify | API keys | F-13 |
| `api/v1/chat/conversations/` (ViewSet) | `ChatViewSet` | chat | session/token | tenant | scoped |
| `api/v1/chat/public/` | `PublicChatView` | chat | **none** | conversation | F-03 |
| `api/v1/chat/embed/<agent_id>/` | `EmbedChatAPI` | chat | none | client-supplied history | AI-03 (prompt injection via history) |
| `api/v1/chat/whatsapp/live/` | `WhatsAppLiveDashboardView` | chat | session | tenant | — |
| `webhooks/chat/` | `WebhookView` | chat | optional secret | conversation | F-14 |
| `webhooks/whatsapp/`, `webhooks/whatsapp/<instance>/` | `WhatsAppWebhookView` | chat | **none** | inbound messages | F-05, F-15 |
| `webhooks/whatsapp/connect/<id>/`, `status/<id>/` | chat.whatsapp_views | chat | to verify | channel | to verify in P0 |
| `ws/whatsapp/<agent_id>/` | `WhatsAppConversationConsumer` | chat | **none** | live conversations | F-04 |
| `api/v1/leads/` (ViewSet) | `LeadViewSet` | leads | session (CSRF disabled) | tenant PII | F-11 |
| `api/v1/leads/appointments/`, `calendars/` | ViewSets | leads | session (CSRF disabled) | tenant | F-07, F-11 |
| `api/v1/leads/my/`, `stats/` | leads.views | leads | session | tenant | — |
| `api/v1/leads/chat/<agent_id>/` | `save_lead_from_chat` | leads | **none** | creates lead | F-08 |
| `api/v1/leads/book-viewing/<agent_id>/` | `book_viewing_from_chat` | leads | **none** | creates appointment | F-08, F-16 |
| `api/v1/leads/ai-agent/<agent_id>/calendar/` | `AIAgentCalendarAPI` | leads | **none** (AllowAny) | creates lead+appointment | F-08 |
| `api/v1/agents/` (ViewSet) | `AgentViewSet` | agents | session/token | own agent | scoped |
| `api/v1/agents/webhooks/*` | webhook_views | agents | session (some csrf_exempt) | outbound webhooks | F-12 |
| `support/*` | support.views | support | session | tickets | admin views: verify staff check in P0 tests |

## C. Change log

| Date | Change | Commit/PR |
|---|---|---|
| 2026-11-02 | Initial audit + matrix created (docs only) | uncommitted |
| 2026-11-02 | `.gitignore`: ignore `.env.*` except `*.example`; fixed corrupted UTF-16 `qr_response.json` line; `git rm --cached .env.production` (file kept on disk) | staged, uncommitted |
