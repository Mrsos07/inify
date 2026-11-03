# Architecture Decision Records

| ADR | Title | Status |
|---|---|---|
| [0001](0001-modular-monolith.md) | Keep Django as a Modular Monolith | Accepted (mandated by spec §0) |
| [0002](0002-tenant-identity-and-roles.md) | Tenant identity = `Agent`; role mapping | Proposed |
| [0003](0003-secrets-and-leak-remediation.md) | Secrets management and leaked-secret remediation | Proposed — needs owner approval |
| [0004](0004-durable-async-broker.md) | Durable broker for background work | Proposed — needs owner decision |
| [0005](0005-public-chat-session-token.md) | Signed session token for public chat | Proposed |

Format: Context → Decision → Consequences → Alternatives. Status flows `Proposed → Accepted | Rejected → Superseded`.
