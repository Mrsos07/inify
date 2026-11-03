# ADR-0004: Durable broker for background work

- **Status:** Proposed — owner decision required before P1
- **Date:** 2026-11-02

## Context
Background work runs in `threading.Thread` inside web workers (outbound webhooks, WhatsApp auto-reconnect, webhook tests). Work is lost on deploy/restart; there is no retry, DLQ or visibility. WhatsApp inbound processing (including the LLM call) runs synchronously inside the webhook request. Deployment target is Render (`render.yaml`, starter plan), with optional Redis (`REDIS_URL`).

## Options

| Option | Durability | Ops cost on Render | Notes |
|---|---|---|---|
| A. Celery + RabbitMQ (e.g. CloudAMQP) | High (durable queues, acks-late, DLX) | extra managed service | Matches spec default |
| B. Celery + Redis broker | Medium (visibility-timeout redelivery; data loss if Redis not persistent) | Redis already planned for Channels/Cache | Spec allows only with documented recovery guarantees |
| C. DB-backed queue (Outbox table + worker polling) | High (PostgreSQL is source of truth) | no new service | Simple, fits Inbox/Outbox (ARC-03); lower throughput |

## Proposed decision
Start with **C (PostgreSQL Outbox/Inbox) for business events** — it is required by ARC-03 anyway and gives durability without new infrastructure — and add **Celery with RabbitMQ (A)** for queue separation (`ai`, `messaging`, `notifications`, `integrations`, `maintenance`) once the owner approves the extra service. Redis remains Cache + Channels.

## Consequences
- P0 does not depend on this decision (P0 adds only a minimal inbound-event dedup table).
- New Render services: worker(s), broker (if A).
