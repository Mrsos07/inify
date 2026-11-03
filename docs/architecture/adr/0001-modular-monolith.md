# ADR-0001: Keep Django as a Modular Monolith

- **Status:** Accepted (mandated by the implementation spec §0 and §ARC-01)
- **Date:** 2026-11-02

## Context
The platform is a single Django 4.2 project with 6 apps (`core`, `properties`, `chat`, `leads`, `agents`, `support`) and a `services/` layer. Business logic is concentrated in very large view modules (`apps/core/views.py` ≈3.1k lines, `apps/chat/views.py` ≈1.8k lines). There is no CI and very limited automated test coverage.

## Decision
- Keep Django/DRF and the existing apps, models, migrations and public routes.
- Introduce **logical** domain boundaries (`identity_tenants`, `properties`, `crm`, `appointments`, `conversations`, `agents`, `billing`, `integrations`, `audit_usage`) as service modules, extracted from views incrementally.
- Do **not** rename apps or move models between apps without an approved migration plan (moving models changes `app_label`/table names).
- Background work moves to independent workers (see ADR-0004), not to separate services.

## Consequences
- Zero-downtime, additive refactors; existing URLs keep working.
- Boundaries are enforced by convention + tests, not by deployment units.

## Alternatives considered
- Microservices split — rejected by the spec; too risky without tests and observability.
