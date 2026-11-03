# Inify Estate AI — Current State Audit

- **Date:** 2026-11-02
- **Branch / commit audited:** `main` @ `30a0126`
- **Scope:** Mandatory Audit (section 2 of `Inify_AI_Coding_Agent_Implementation_Instructions.md`). No application code was modified during this audit.
- **Method:** Static review of the repository + local baseline run (dummy, non-secret env values).

> Secret values were **never printed or copied** during this audit. Only key names and value lengths were inspected.

---

## 1. Baseline evidence (local run)

| Check | Command | Result |
|---|---|---|
| Django system check | `python manage.py check` | `System check identified no issues (0 silenced).` |
| Deploy check (`DEBUG=False`) | `python manage.py check --deploy` | `System check identified no issues (0 silenced).` |
| Pending migrations | `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| Existing automated tests | `python manage.py test test_whatsapp_fixes` | `Ran 23 tests ... OK` |
| Local interpreter | `venv\Scripts\python.exe --version` | Python 3.13.15 (Docker image uses 3.11 → version drift) |

Observations from the baseline run:
- Startup **requires** `DJANGO_SECRET_KEY`, `ADMIN_SECRET_KEY` and a valid Fernet `FIELD_ENCRYPTION_KEY`; otherwise import fails (`encrypted_model_fields`).
- The file log handler (`config/settings.py:326-331`) has no `encoding`, which produces `UnicodeEncodeError` logging errors on Windows when log messages contain emoji (seen during the test run). The tests still pass.

---

## 2. Architecture snapshot

- **Framework:** Django 4.2 + DRF, Channels (Daphne in `INSTALLED_APPS`), django-allauth (Google), WhiteNoise, Cloudinary, `encrypted_model_fields`.
- **Apps:** `apps.core` (pages, auth, admin panel APIs, subscription, StreamPay webhook, WhatsApp dashboard APIs), `apps.properties`, `apps.chat` (conversations, public/embed chat, n8n webhook, WhatsApp webhook, WebSocket consumer), `apps.leads` (leads, appointments, calendars), `apps.agents` (Agent = tenant, settings, subscriptions, API keys, webhooks, team, token usage), `apps.support`.
- **Services layer (`services/`):** 3 separate OpenAI clients (`NewraAIService`, `OpenAIService`, `SmartAgentService`), `agent_tools`, `rag_service`, `intent_service`, lead capture/extraction, `whatsapp_service` (Evolution API), `whatsapp_session_manager`, `streampay_service`, `email_service`, `excel_import_service`.
- **Tenant model:** `apps.agents.models.Agent` (one per user, `OneToOne` with `User`). `TeamMember` links an extra `User` (who has their *own* `Agent`) to an `owner_agent`; roles: `marketer`, `viewer`. There is no separate Tenant/Organization model.
- **Async/background:** no broker or worker. Background work is done with `threading.Thread` inside web workers:
  - `apps/agents/webhook_service.py:128` (outbound webhooks)
  - `apps/agents/webhook_views.py:170` (webhook test)
  - `apps/chat/whatsapp_views.py:112` (auto-reconnect)
  - `apps/core/whatsapp_views.py:528` (auto-reconnect)
- **Realtime:** `CHANNEL_LAYERS` = `InMemoryChannelLayer` (`config/settings.py:142-146`). Docker `CMD` runs **gunicorn WSGI** (`Dockerfile` last line), so the ASGI/WebSocket route (`config/asgi.py`, `apps/chat/routing.py`) is **not served in the container**.
- **Cache:** Redis if `REDIS_URL` is set, otherwise `LocMemCache` (per-process; dedup/rate-limit keys are not shared across workers).
- **Database:** `DATABASE_URL` (Render) → PostgreSQL, or `USE_POSTGRES`, else SQLite.
- **Deploy:** `Dockerfile` (single stage, runs as root, `COPY . .`, migrations + collectstatic on container start), `render.yaml`, `build.sh`, `docker-compose.production.yml`, `docker-compose.evolution.yml`, `scripts/` (nginx, systemd, deploy).
- **CI:** none (no `.github/workflows`).
- **Tests:** no `tests.py`/`tests/` in any app. Root-level `test_booking.py`, `test_booking_tool.py`, `test_restrictions.py` are manual scripts that call a live server with a hard-coded agent id; `fix_booking.py` / `check_db.py` are ad-hoc DB scripts. Only `test_whatsapp_fixes.py` is a real Django `TestCase` suite (23 tests).

---

## 3. Located components (requested by the spec)

| Component | Location |
|---|---|
| `PublicChatView` | `apps/chat/views.py:761-832` (route `api/v1/chat/public/`) |
| `EmbedChatAPI` | `apps/chat/views.py:835+` (route `api/v1/chat/embed/<agent_id>/`) |
| n8n `WebhookView` | `apps/chat/views.py:596-758` (route `webhooks/chat/`) |
| `get_property_appointments` | `apps/properties/views.py:917-962` (route `api/v1/properties/<id>/appointments/`) |
| `check_admin_access` | `apps/core/views.py:1450-1466` |
| `admin_login` | `apps/core/views.py:1469-1520` |
| `NewraAIService` | `services/ai_service.py:17` |
| `OpenAIService` | `services/openai_service.py:15` |
| `SmartAgentService` | `services/smart_agent_service.py:19` |
| StreamPay webhook | `apps/core/views.py:2563-2805` (route `webhooks/streampay/`), signature: `services/streampay_service.py:317-346` |
| Evolution (WhatsApp) webhook — **routed** | `apps/chat/whatsapp_views.py:25+` `WhatsAppWebhookView` (routes `webhooks/whatsapp/` and `webhooks/whatsapp/<instance_name>/`) |
| Evolution webhook — **duplicate, not routed** | `apps/core/whatsapp_views.py:453` `whatsapp_webhook` (exercised only by `test_whatsapp_fixes.py`) |
| WebSocket consumer | `apps/chat/consumers.py:15` (route `ws/whatsapp/<agent_id>/`) |
| `CHANNEL_LAYERS` | `config/settings.py:142-146` |
| Outbound webhooks | `apps/agents/webhook_service.py`, `apps/agents/webhook_views.py` |
| Partner API (API key) | `apps/properties/api_views.py` (routes `api/v1/properties/ext/...`) |
| Env files | `.env.example`, `.env.production`, `.env.production.secure` (all tracked by Git) |

---

## 4. Endpoint inventory (summary)

Full per-route matrix is in `docs/implementation/traceability-matrix.md` §B. Classes:

| Class | Auth used today | Examples |
|---|---|---|
| Dashboard pages | Django session (`login_required`) | `dashboard/*`, `profile/`, `subscription/` |
| Dashboard JSON APIs (session) | session, many with `@csrf_exempt` | `api/v1/properties/save/`, `api/team/*`, `api/profile/*`, `api/whatsapp/*`, `api/subscription/*` |
| DRF ViewSets | Session/Token; `LeadViewSet`, `ViewingAppointmentViewSet`, `PropertyCalendarViewSet` use `CsrfExemptSessionAuthentication` | `api/v1/leads/`, `api/v1/leads/appointments/`, `api/v1/chat/conversations/` |
| Admin panel APIs | `check_admin_access` (session flag set by env username/password **or** static `X-Admin-Key`) | `api/admin/*`, `api/settings/save/` |
| Public (anonymous) | none / `agent_id` in URL or body | `api/v1/chat/public/`, `api/v1/chat/embed/<id>/`, `api/v1/leads/chat/<id>/`, `api/v1/leads/book-viewing/<id>/`, `api/v1/leads/ai-agent/<id>/calendar/`, `api/v1/properties/<id>/book-viewing/`, `api/v1/properties/<id>/viewing-calendar/`, `api/v1/properties/<id>/appointments/`, `api/v1/properties/agent/<id>/`, `api/settings/`, `api/agent/<id>/conversation/` |
| Partner API | `X-API-Key` header **or `?api_key=` query**; plaintext key lookup | `api/v1/properties/ext/*` |
| Inbound webhooks | StreamPay: HMAC (fail-open if secret unset); Evolution: none; n8n: optional secret | `webhooks/streampay/`, `webhooks/whatsapp/...`, `webhooks/chat/` |
| WebSocket | none enforced in consumer | `ws/whatsapp/<agent_id>/` |
| Test/debug in prod | session | `test/add-property/` |

---

## 5. Findings (prioritised)

Severity: **Critical** = exploitable now, cross-tenant/PII/financial impact. **High** = serious, needs a precondition. **Medium/Low** = hardening.

### 5.1 Critical

| ID | Finding | Evidence | Impact |
|---|---|---|---|
| F-01 | Production env files tracked in Git and shipped in the Docker image | `git ls-files` lists `.env.production`, `.env.production.secure`; `.gitignore` only ignores `.env`, `.env.local`, `.env.*.local`; `.dockerignore` does not exclude them; `Dockerfile` does `COPY . .`. `.env.production` contains non-placeholder values for `DJANGO_SECRET_KEY`, `ADMIN_SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `FIELD_ENCRYPTION_KEY`, `DB_PASSWORD`, `RESEND_API_KEY`. These two files appear in 6 commits of history. `.env.example` has a 32-char `EVOLUTION_API_KEY` that does not look like a placeholder (needs owner verification). `docker-compose.evolution.yml:8,35` contain literal DB credentials. | Anyone with repo/image access can forge sessions (SECRET_KEY), log in to the admin panel, decrypt encrypted PII fields (FIELD_ENCRYPTION_KEY), and send email as the company. **Rotation is required regardless of code fixes.** |
| F-02 | Appointment PII exposed to anonymous users | `apps/properties/views.py:917-962`: no authentication, no ownership check; returns `client_name`, `client_phone`, `notes` for any property UUID. Property UUIDs are public via `api/v1/properties/public/` and `api/v1/properties/agent/<id>/`. | Any visitor can enumerate customers' names/phones for every tenant. |
| F-03 | Public chat conversation hijack (cross-tenant) | `apps/chat/views.py:795-799`: `Conversation.objects.get(id=conversation_id)` is not scoped to `agent`; `conversation_id` alone is treated as proof of ownership. | Knowing a conversation UUID lets an attacker append messages to another tenant's conversation and receive AI replies built from its history. |
| F-04 | WebSocket live dashboard has no authentication or tenant check | `apps/chat/consumers.py:21-40` accepts any connection; `get_conversation_details` (`:137-159`) and `send_manager_message` (`:162-192`) load `Conversation` by id **without** agent scope and send WhatsApp messages from that tenant's number. | Read any tenant's WhatsApp conversations and send messages as any tenant. (Currently partially masked because the Docker image serves WSGI only — becomes live as soon as ASGI is deployed.) |
| F-05 | Evolution (WhatsApp) webhook is unauthenticated | `apps/chat/whatsapp_views.py:34-71`: only checks that `instance_name` exists; instance names are predictable (`inify_<name>_<first 8 hex of agent id>`, `apps/core/whatsapp_views.py:234`); the global route reads the instance from the body. | Forged inbound messages trigger AI replies sent from the tenant's WhatsApp number to arbitrary phones (abuse, cost, reputational risk), forged connection/QR state changes. |
| F-06 | Payment webhook fail-open and replayable | `apps/core/views.py:2585`: signature checked **only if** `STREAMPAY_WEBHOOK_SECRET` is set and not the placeholder; no timestamp tolerance (`services/streampay_service.py:332-343`); no event-id dedup; amount check skipped when amount is missing/0 (`views.py:2615`); no currency check; `INVOICE_COMPLETED` replays extend `end_date` each time (`:2677-2711`). | If the secret is ever missing → free subscription activation by forged POST. With a valid captured event → unlimited renewals by replay. |
| F-07 | BOLA on appointment / calendar creation | `apps/leads/serializers.py:277-308` (`ViewingAppointmentCreateSerializer`) and `PropertyCalendarSerializer` accept `lead`/`property` primary keys from **any** tenant (default unrestricted querysets). | An authenticated tenant can create appointments against other tenants' leads/properties and read back their data through the response serializer. |
| F-08 | Public lead/booking endpoints accept cross-tenant property ids | `apps/leads/views.py:936` (`save_lead_from_chat`) and `:1035` (`book_viewing_from_chat`) use `Property.objects.get(id=...)` without `agent=agent`; `AIAgentCalendarAPI` (`:516-735`) is `AllowAny` with no rate limit and writes leads/appointments for any agent id. | Data pollution across tenants, tampering with `interested_count`, spam bookings. |

### 5.2 High

| ID | Finding | Evidence |
|---|---|---|
| F-09 | Admin authorization relies on a static shared key / env credentials, not Django identities | `check_admin_access` (`apps/core/views.py:1450-1466`) accepts `X-Admin-Key == ADMIN_SECRET_KEY` (non-constant-time `==`); `admin_login` compares env `ADMIN_USERNAME`/`ADMIN_PASSWORD` in plaintext (`:1499-1504`); login rate-limit key uses the spoofable `X-Forwarded-For` first hop (`:1477-1481`). No MFA, no per-admin audit trail. |
| F-10 | Global system prompt exposed publicly; agent system prompt & policies exposed publicly | `get_global_settings` (`apps/core/views.py:1370-1396`) has no auth; `get_agent_properties` (`apps/properties/views.py:588`) returns `systemPrompt`. Both are consumed by `templates/embed.html` and `templates/chat-live.html` (client-side prompt assembly), so removal needs a compatibility step. |
| F-11 | `csrf_exempt` used 59 times across `apps/` (most on session-authenticated state-changing endpoints) | e.g. `apps/properties/views.py:151,352,370,386,460,845,998`; `apps/core/views.py` (profile, password change, team, subscription, admin APIs); `apps/core/whatsapp_views.py:107,206,383,416,879`; `CsrfExemptSessionAuthentication` in `apps/leads/views.py:26-29`. `SESSION_COOKIE_SAMESITE='Lax'` mitigates most cross-site POSTs, but not same-site subdomains or older browsers. `ACCOUNT_LOGOUT_ON_GET=True` (`settings.py:358`). |
| F-12 | Outbound webhooks: SSRF and no durability | `apps/agents/webhook_views.py:58,113` allow any `http(s)://` URL; `webhook_service.py:63-64` uses `urlopen` (follows redirects, resolves private/loopback/metadata IPs); dispatched in daemon threads (`:128`) → lost on worker restart; no retry/DLQ. Signature has no timestamp/event-id. |
| F-13 | API keys: query-string transport and plaintext storage | `apps/properties/api_views.py:20` accepts `?api_key=`; `APIKey.key` is stored plaintext (`apps/agents/models.py:573`) and looked up directly; no scopes; no per-key rate limit. |
| F-14 | n8n webhook auth is optional | `apps/chat/views.py:623`: if `agent.webhook_secret` is empty, any caller can drive the agent's AI and create conversations; non-constant-time comparison. |
| F-15 | PII/raw payload logging | `apps/chat/whatsapp_views.py:40-54` appends the **raw webhook body** to `webhook_debug.log` and prints it; `apps/properties/views.py:157-158` prints user info; several handlers return `str(e)` to clients (e.g. `properties/views.py:914,962`, `leads/views.py:967`). |
| F-16 | Booking race condition | `book_property_viewing` (`apps/properties/views.py:752-787`), `book_viewing_from_chat` (`apps/leads/views.py:1069-1095`), `AIAgentCalendarAPI.post` use `exists()`/`check_availability` then `create()` with no transaction/lock and no DB constraint on `ViewingAppointment`. |
| F-17 | Production container cannot serve WebSockets; in-memory channel layer | `Dockerfile` CMD = `gunicorn ... config.wsgi:application`; `CHANNEL_LAYERS` in-memory. Live dashboard/WS breaks across replicas. |
| F-29 | Lead de-duplication silently broken (functional bug) | `Lead.phone/email/whatsapp` are `EncryptedCharField`/`EncryptedEmailField` (`apps/leads/models.py:65-67`); the library encrypts only in `get_db_prep_save`, so `filter(phone=...)`/`get_or_create(phone=...)` compare plaintext with ciphertext and **never match**. Affected: `apps/properties/views.py:763`, `apps/leads/views.py:897,1017`, `services/agent_tools.py:646`, `services/lead_capture_service.py:282`, `services/lead_extraction_service.py:334,336`, `apps/core/whatsapp_views.py:593` (and similar). **Verified** with a throwaway Django test: `filter_matches=0 get_or_create_created=True total=2`. Fix pattern already exists for `Agent.phone_hash` (`apps/agents/models.py:30`). |

### 5.3 Medium / Low

| ID | Finding | Evidence |
|---|---|---|
| F-18 | Anonymous counter tampering | `increment_conversation` (`apps/core/views.py:1981-2003`) — public, no rate-limit. |
| F-19 | Debug/test endpoint in production | `test/add-property/` (`apps/core/views.py:1250-1365`). |
| F-20 | Email verification disabled; login/logout on GET | `ACCOUNT_EMAIL_VERIFICATION='none'`, `ACCOUNT_LOGIN_ON_GET=True`, `SOCIALACCOUNT_LOGIN_ON_GET=True` (`settings.py:357-367`). Needs product decision. |
| F-21 | Global OpenAI key stored plaintext in DB | `GlobalSettings.openai_api_key` is a plain `CharField` (`apps/agents/models.py:307`). |
| F-22 | Fragmented AI stack; incomplete metering | 3 OpenAI clients; `TokenUsage.log` only at `ai_service.py:149`, `openai_service.py:218,257`. Unmetered calls: `ai_service.py:214,366,403`, `smart_agent_service.py:163,215`. No prompt versioning, no iteration/deadline limits centrally enforced. |
| F-23 | Duplicate code paths | Two Evolution webhook handlers (routed `apps/chat/whatsapp_views.py` vs unrouted `apps/core/whatsapp_views.py:453`); `WhatsAppService.set_webhook` defined twice (`services/whatsapp_service.py:189` and `:406` — the second silently overrides the first); duplicate `update_status` action in `LeadViewSet` (`apps/leads/views.py:63` and `:113`). |
| F-24 | Dedup relies on cache only (10 min TTL), per-process with LocMem | `apps/chat/whatsapp_views.py:177-186`. |
| F-25 | Container hardening | Runs as root; single stage with `build-essential`; migrations run on every container start; Python 3.11 (image) vs 3.13 (local). |
| F-26 | Dependency ranges unpinned (`>=`) and dev/test deps in prod requirements | `requirements.txt` (e.g. `django-debug-toolbar`, `pytest*`). No lock file, no dependency scanning. |
| F-27 | Logging config | File handler without `encoding='utf-8'` (`settings.py:326-331`); not structured; no redaction. |
| F-28 | `ALLOWED_HOSTS` default includes `host.docker.internal`; `CSRF_TRUSTED_ORIGINS` default includes `https://*.onrender.com` | `settings.py:21,60-66`. |

---

## 6. Data model notes

- No DB-level uniqueness for appointments (`ViewingAppointment`) → required for DOM-01.
- `Lead.phone` is encrypted with non-deterministic Fernet, so no uniqueness/lookup is possible on it (see F-29). A deterministic `phone_hash` (HMAC with a dedicated key, normalised phone) plus a unique constraint `(agent, phone_hash)` is required; existing duplicates must be reported before the constraint is added.
- `Subscription` has `payment_id`/`invoice_id`/`subscription_id` but no unique constraints and no processed-event ledger.
- 25 migrations in `agents`, 6 in `leads`, 6 in `properties`, 1 in `chat`, 1 in `support`; `makemigrations --check` clean.

---

## 7. What already works and must be preserved

- Session-scoped DRF querysets for `Lead`, `ViewingAppointment` (list/retrieve), `PropertyCalendar`, `Conversation`, `Agent`, `Property` (dashboard) correctly filter by `request.user.agent_profile`.
- StreamPay HMAC verification uses `hmac.compare_digest` when the secret is configured; amount-vs-plan check exists (commit `621c83b`).
- WhatsApp subscription-expiry auto-disconnect + reconnect rate limiting (23 passing tests).
- Admin login reCAPTCHA + attempt lockout.
- Production security headers (HSTS, secure cookies, SSL redirect) when `DEBUG=False`.
- Outbound webhooks already sign with HMAC-SHA256.

---

## 8. Conflicts between the spec and the code (recorded per §0)

| Spec item | Code reality | Proposed safe resolution |
|---|---|---|
| Roles `platform_admin`, `tenant_owner`, `tenant_admin`, `agent_operator`, `sales`, `read_only` | Only `Agent` owner + `TeamMember.role ∈ {marketer, viewer}`; platform admin = env credentials | Map: `tenant_owner`=Agent owner, `sales`/`agent_operator`=`marketer`, `read_only`=`viewer`, `platform_admin`=Django `is_superuser`/group. Add `tenant_admin` only on approval. (ADR-0002) |
| `tenant_id` | No Tenant model; `Agent` is the tenant | Treat `Agent.id` as `tenant_id` (ADR-0002). No model rename. |
| Durable broker (RabbitMQ) | Nothing exists; Render plan has no broker | Decision needed (ADR-0004, Proposed). |
| Partner API under `/api/v1/ext/` (docstring) | Actually mounted at `/api/v1/properties/ext/` | Keep current path; document; add alias only if approved. |
