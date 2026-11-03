# ADR-0002: Tenant identity = `Agent`; role mapping

- **Status:** Proposed
- **Date:** 2026-11-02

## Context
There is no Tenant/Organization model. Every `User` has one `apps.agents.models.Agent` (`OneToOneField`), and all business rows (`Property`, `Lead`, `Conversation`, `ViewingAppointment`, `WhatsAppInstance`, `APIKey`, `Webhook`, `Subscription`, `TokenUsage`) reference `Agent`. Enterprise teams are modelled by `TeamMember(owner_agent, user, role ∈ {marketer, viewer})`; each member also owns their own `Agent`.
Platform admin is currently an env username/password or a static `X-Admin-Key` (`apps/core/views.py:1450-1520`).

## Decision
1. **`tenant_id` := `Agent.id`.** No new model or rename in P0.
2. Tenant context is resolved **server-side only**:
   - Session/Token: `request.user.agent_profile`.
   - Partner API: the `Agent` owning the verified API key.
   - WhatsApp: the `Agent` owning the `WhatsAppInstance` matched by instance **and** a verified per-instance secret.
   - Public chat: the `Agent` bound inside a signed session token (ADR-0005); the URL/body `agent_id` is only used to *start* a new anonymous conversation for an active agent.
3. A single helper module (`apps/core/permissions.py`, proposed) exposes `get_tenant(request)`, `require_tenant_owner(obj)` and DRF permission classes; all new/changed endpoints use it.
4. Role mapping (spec → current):

| Spec role | Current equivalent | Enforcement |
|---|---|---|
| `platform_admin` | Django `is_superuser` or group `platform_admin` | replaces `X-Admin-Key` (legacy flag during transition) |
| `tenant_owner` | `Agent` owner user | default for own data |
| `tenant_admin` | — | add later only if approved |
| `agent_operator` / `sales` | `TeamMember.role='marketer'` | read/write own member `Agent` data |
| `read_only` | `TeamMember.role='viewer'` | read only |

## Consequences
- No schema changes required for isolation fixes in P0.
- A future Organization model (grouping owner + members) remains possible via an additive migration.

## Open questions for the owner
- Should an enterprise owner be able to read team members' leads/conversations (today each member is a separate `Agent`)?
- Is `tenant_admin` needed?
