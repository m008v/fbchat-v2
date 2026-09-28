# fbchat-v2 Provider REST API

The HTTP service is the private process boundary between SocialManager and the
unofficial Facebook client. Frontend applications must call SocialManager;
they must not call this provider service directly.

## Run locally

Set credentials before starting Compose:

```bash
export FBCHAT_API_USERNAME=provider
export FBCHAT_API_PASSWORD='replace-with-a-long-random-secret'
docker compose up --build
```

The Compose service listens on `http://127.0.0.1:8088`. Open `/` for the
administration portal and `/docs` for the authenticated OpenAPI explorer.

## Authentication

Every portal and `/api/v1` route uses HTTP Basic authentication when
`FBCHAT_API_AUTH_REQUIRED=true`. Only `/healthz` and `/readyz` are public.

| Environment variable | Purpose | Image default |
|---|---|---|
| `FBCHAT_API_AUTH_REQUIRED` | Require HTTP Basic authentication | `true` |
| `FBCHAT_API_USERNAME` | API username | unset |
| `FBCHAT_API_PASSWORD` | API password | unset |

Readiness returns `503` when authentication is required but credentials are
missing. Never reuse Facebook credentials as API credentials.

## Response envelope

Successful responses follow the GOWA-style envelope:

```json
{
  "code": "SUCCESS",
  "message": "Provider sessions.",
  "results": []
}
```

Errors return a stable `code` and a sanitized `message`. Validation responses
never echo rejected request values because those values can contain cookies.

## Available endpoints

| Method | Path | Authentication | Purpose |
|---|---|---|---|
| `GET` | `/healthz` | public | Process liveness |
| `GET` | `/readyz` | public | Bridge, API auth, and portal readiness |
| `GET` | `/` | Basic | Administration portal |
| `GET` | `/docs` | Basic | OpenAPI explorer |
| `GET` | `/api/v1/app/info` | Basic | Version and capabilities |
| `GET` | `/api/v1/sessions` | Basic | List provider-owned session IDs |
| `POST` | `/api/v1/sessions` | Basic | Authenticate Facebook cookies |
| `POST` | `/api/v1/sessions/{sessionId}/validate` | Basic | Revalidate a session |
| `DELETE` | `/api/v1/sessions/{sessionId}` | Basic | Disconnect and clear a session |
| `GET` | `/api/v1/sessions/{sessionId}/threads` | Basic | List sanitized conversations |
| `POST` | `/api/v1/sessions/{sessionId}/messages/text` | Basic | Send a text message |
| `GET` | `/api/v1/webhook` | Basic | Read the global webhook configuration |
| `PUT` | `/api/v1/webhook` | Basic | Persist the global webhook configuration |
| `DELETE` | `/api/v1/webhook` | Basic | Clear the global webhook configuration |

Create-session input:

```json
{
  "label": "Marketplace account",
  "cookies": [
    {"name": "c_user", "value": "..."},
    {"name": "xs", "value": "..."}
  ]
}
```

The response contains a generated `sessionId`, label, status, and timestamps.
It never contains cookie values, Facebook account IDs, provider URLs, or the
private `dataFB` object.

List conversations:

```http
GET /api/v1/sessions/{sessionId}/threads
```

The response is intentionally reduced to stable conversation fields:
`threadId`, `type`, `name`, `unreadCount`, `updatedAt`, `archived`, and
`marketplace`. Provider image URLs and raw Facebook metadata are omitted.

Send a text message:

```json
{
  "threadId": "1234567890",
  "threadType": "user",
  "text": "Hello from SocialManager",
  "replyToMessageId": null
}
```

`threadType` accepts `user` or `group`. A successful response includes the
provider message ID, destination thread ID, status, and timestamp. Provider
failures are mapped to a sanitized `502 PROVIDER_ERROR` response.

## Current persistence model

Sessions are process-local and memory-only in this first milestone. Restarting
the container disconnects them. Persistent sessions remain disabled until an
encrypted-at-rest store with key rotation and tenant isolation is implemented.

## Global webhook configuration

The portal stores one webhook configuration for every provider session. The
webhook URL, enabled state, and event allowlist are persisted in
`FBCHAT_STATE_DIR/webhook.json`; they are not configured through environment
variables.

```json
{
  "enabled": true,
  "url": "https://socialmanager.example.com/hooks/facebook",
  "events": ["message.received", "session.status"],
  "secret": "replace-with-a-signing-secret"
}
```

The optional signing secret is encrypted with a private Fernet key generated
inside the state volume. API responses only return `secretConfigured`; they
never return the cleartext or ciphertext. Sending events is intentionally not
enabled yet: delivery requires a bounded queue, retries, signing, timeouts, and
SSRF controls.

## Media boundary

Future media endpoints must return a stable SocialManager-owned `mediaId`.
Facebook CDN URLs, filesystem paths, encryption metadata, attachment keys, and
provider media identifiers are private implementation details and must never
appear in a public DTO, portal response, webhook, or realtime event.
