# ADR-0005: Signed session token for public chat

- **Status:** Proposed
- **Date:** 2026-11-02

## Context
`PublicChatView` (`apps/chat/views.py:761-832`) accepts a client-supplied `conversation_id` and loads it **without** agent scoping. Knowing a UUID is the only proof of ownership (finding F-03). Clients: `templates/chat/widget.html` and `static/js/chat-widget.js` send `conversation_id` and store the returned one.

## Decision
- On conversation creation, the server returns `session_token` = `django.core.signing.TimestampSigner(salt='inify.public_chat').sign_object({'c': conversation_id, 'a': agent_id, 'n': random_nonce})`.
- On subsequent messages the client sends `session_token`. The server verifies signature and age (`PUBLIC_CHAT_TOKEN_MAX_AGE`, default 7 days), then loads `Conversation(id=c, agent_id=a)` and requires `a == agent_id` from the request.
- **Backward compatibility:** requests that carry only `conversation_id` (old cached widget JS) are treated as a **new** conversation instead of failing; the response keeps `conversation_id` and adds `session_token`. Widget JS is updated to send the token.
- Token is never logged.

## Consequences
- Old embedded widgets keep working but lose continuity until they load the new JS.
- No DB migration needed (stateless signed token; rotation of `SECRET_KEY` invalidates tokens → new conversation, acceptable).

## Alternatives
- Random opaque token stored in DB (hash) — allows server-side revocation; can be added later if needed.
