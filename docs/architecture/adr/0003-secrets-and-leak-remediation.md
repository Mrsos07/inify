# ADR-0003: Secrets management and leaked-secret remediation

- **Status:** Proposed — requires owner approval for rotation and any history rewrite
- **Date:** 2026-11-02

## Context
`.env.production` and `.env.production.secure` are tracked in Git (6 commits) and copied into the Docker image (`COPY . .`, not excluded by `.dockerignore`). `.env.production` holds non-placeholder values for `DJANGO_SECRET_KEY`, `ADMIN_SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `FIELD_ENCRYPTION_KEY`, `DB_PASSWORD`, `RESEND_API_KEY`. `docker-compose.evolution.yml` contains literal DB credentials. `.env.example` contains a non-placeholder-looking `EVOLUTION_API_KEY` (to be verified by the owner).

## Decision
1. **Stop the bleed (code, reversible):** untrack the files (`git rm --cached`, files stay on disk), ignore `.env*` except `*.example`, exclude them in `.dockerignore`, add `.env.production.example` with fake values, replace compose literals with `${VAR}`.
2. **Prevent regressions:** Gitleaks in CI on every push/PR; image test asserting no `.env*` (other than examples) inside the image.
3. **Rotate (owner action, irreversible):** treat every value in those files as compromised. Order:
   1. `FIELD_ENCRYPTION_KEY` — **must not** simply be replaced: existing encrypted rows would become unreadable. Use `FIELD_ENCRYPTION_KEY` as a comma-separated list (new key first, old key second — supported by `encrypted_model_fields` via `MultiFernet`), run a re-encryption management command, then remove the old key.
   2. `DJANGO_SECRET_KEY` (invalidates sessions/reset tokens — schedule a low-traffic window).
   3. `ADMIN_SECRET_KEY`, `ADMIN_USERNAME`/`ADMIN_PASSWORD` (superseded by Django admin identities, ADR-0002).
   4. `DB_PASSWORD`, `RESEND_API_KEY`, Evolution API key, StreamPay keys/webhook secret, OpenAI key, Google OAuth secret, Cloudinary secret.
4. **History cleanup (plan only):** `git filter-repo --path .env.production --path .env.production.secure --invert-paths` on a fresh mirror clone, then force-push. Impact: all collaborators must re-clone; open PRs/forks keep old history; GitHub caches may retain blobs (contact support). **Rotation is mandatory even after history cleanup.** Not executed without explicit approval.

## Consequences
- Deployments must provide all secrets via Render env vars / secret manager.
- Local development uses `.env` (ignored) created from `.env.example`.

## Alternatives
- Only rotating without history rewrite — acceptable if the owner prefers to avoid a force push; leaked values become useless after rotation.
