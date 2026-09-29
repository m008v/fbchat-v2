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
| `GET` | `/ws` | Basic / Query | Real-time WebSocket event stream (supports `?sessionId=...`) |
| `GET` | `/api/v1/app/info` | Basic | Version, capabilities list, and capability matrix |
| `GET` | `/api/v1/app/status` | Basic | Service status, active sessions count, and readiness check |
| `GET` | `/api/v1/diagnostics` | Basic | Readiness components, webhook telemetry, and audit logs |
| `GET` | `/api/v1/sessions` | Basic | List provider-owned sessions (supports `?tenantId=...&detailed=true`) |
| `POST` | `/api/v1/sessions` | Basic | Authenticate Facebook cookies and create encrypted session |
| `GET` | `/api/v1/sessions/{sessionId}/status` | Basic | Detailed operational telemetry for a session |
| `POST` | `/api/v1/sessions/{sessionId}/validate` | Basic | Revalidate a session with Facebook |
| `DELETE` | `/api/v1/sessions/{sessionId}` | Basic | Disconnect and clear an encrypted session from disk |
| `POST` | `/api/v1/sessions/{sessionId}/listen/start` | Basic | Start background listener worker for inbound events |
| `POST` | `/api/v1/sessions/{sessionId}/listen/stop` | Basic | Stop background listener worker |
| `GET` | `/api/v1/sessions/{sessionId}/listen/status` | Basic | Query active listener status (`listening` or `idle`) |
| `GET` | `/api/v1/sessions/{sessionId}/threads` | Basic | List sanitized conversations |
| `POST` | `/api/v1/sessions/{sessionId}/messages/text` | Basic | Send a text message |
| `POST` | `/api/v1/sessions/{sessionId}/messages/media` | Basic | Send an attachment by staged `media_id` with optional caption |
| `POST` | `/api/v1/sessions/{sessionId}/messages/reaction` | Basic | Add or remove an emoji reaction on a message |
| `POST` | `/api/v1/sessions/{sessionId}/messages/unsend` | Basic | Revoke / unsend a sent message |
| `GET` | `/api/v1/sessions/{sessionId}/users/{userId}` | Basic | Lookup sanitized user profile |
| `GET` | `/api/v1/sessions/{sessionId}/search` | Basic | Search users by query string (`?q=...`) |
| `POST` | `/api/v1/sessions/{sessionId}/privacy/block` | Basic | Block or unblock a Facebook user |
| `GET` | `/api/v1/sessions/{sessionId}/marketplace/{itemId}` | Basic | Inspect marketplace product listing details |
| `POST` | `/api/v1/media/upload` | Basic | Upload and stage media (JSON base64 or raw binary stream) |
| `GET` | `/api/v1/media` | Basic | List metadata of staged media files |
| `GET` | `/api/v1/media/{mediaId}` | Basic | Download raw staged media file content |
| `GET` | `/api/v1/media/{mediaId}/info` | Basic | Inspect staged media metadata |
| `DELETE` | `/api/v1/media/{mediaId}` | Basic | Delete staged media file |
| `GET` | `/api/v1/webhook` | Basic | Read the global webhook configuration and delivery stats |
| `PUT` | `/api/v1/webhook` | Basic | Persist the global webhook configuration |
| `DELETE` | `/api/v1/webhook` | Basic | Clear the global webhook configuration |
| `POST` | `/api/v1/webhook/test` | Basic | Send a test probe to verify webhook URL, latency, and signature |

Create-session input:

```json
{
  "label": "Marketplace account",
  "tenantId": "default",
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
GET /api/v1/sessions/{sessionId}/threads?limit=20
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

React to a message:

```http
POST /api/v1/sessions/{sessionId}/messages/reaction
```
```json
{
  "messageId": "mid.1234567890",
  "reaction": "❤️"
}
```

Pass `reaction: null` to remove an existing reaction.

Unsend / Revoke a message:

```http
POST /api/v1/sessions/{sessionId}/messages/unsend
```
```json
{
  "messageId": "mid.1234567890"
}
```

Lookup user profile:

```http
GET /api/v1/sessions/{sessionId}/users/{userId}
```

Returns sanitized profile: `userId`, `name`, `profileUrl`, `avatarUrl`, `isFriend`, and `gender`.

Search users:

```http
GET /api/v1/sessions/{sessionId}/search?q=Alice&limit=10
```

Block / unblock user:

```http
POST /api/v1/sessions/{sessionId}/privacy/block
```
```json
{
  "userId": "100012345678",
  "blocked": true
}
```

Inspect marketplace listing:

```http
GET /api/v1/sessions/{sessionId}/marketplace/{itemId}
```

Returns sanitized listing details: `itemId`, `title`, `price`, `currency`, `description`, `location`, `sellerId`, and `isSold`.

Send a media attachment:

```http
POST /api/v1/sessions/{sessionId}/messages/media
```
```json
{
  "threadId": "1234567890",
  "threadType": "user",
  "mediaId": "med_a1b2c3d4e5f67890",
  "text": "Check out this document"
}
```

Upload / Stage a media file (JSON with base64):

```http
POST /api/v1/media/upload
```
```json
{
  "filename": "invoice.pdf",
  "contentType": "application/pdf",
  "dataBase64": "JVBERi0xLjQK..."
}
```

Alternatively, upload via raw binary stream:

```http
POST /api/v1/media/upload
Content-Type: image/png
X-File-Name: photo.png

<raw binary bytes>
```

Response:

```json
{
  "code": "SUCCESS",
  "message": "Media uploaded and staged successfully.",
  "results": {
    "mediaId": "med_a1b2c3d4e5f67890",
    "filename": "photo.png",
    "contentType": "image/png",
    "sizeBytes": 45820,
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "createdAt": "2026-09-29T00:30:00.000Z"
  }
}
```

Session Listener management:

```http
POST /api/v1/sessions/{sessionId}/listen/start
POST /api/v1/sessions/{sessionId}/listen/stop
GET /api/v1/sessions/{sessionId}/listen/status
```

Realtime WebSocket stream:

```http
GET /ws?sessionId=sess_123456
```

WebSocket clients authenticate via:
- Standard `Authorization: Basic <base64(user:pass)>` header (for programmatic clients)
- Query parameter `?token=<password>` (for web applications / browser native `WebSocket`)
- Query parameter `?authorization=<base64(user:pass)>` (matches GOWA browser WebSocket pattern)

Event frame payload:

```json
{
  "event": "message.received",
  "sessionId": "sess_123456",
  "timestamp": "2026-09-29T00:31:00.000Z",
  "data": {
    "messageId": "mid.123456789",
    "threadId": "987654321",
    "senderId": "100012345",
    "text": "Hello there",
    "timestamp": 1727579460000
  }
}
```

Test webhook probe:

```http
POST /api/v1/webhook/test
```

Sends an immediate test event through the dispatcher and returns latency in milliseconds, HTTP response status, and whether HMAC signature was generated.

## Encrypted Persistence Model

Sessions are persisted securely on disk with:
1. **Fernet Key Protection**: Stored in `FBCHAT_STATE_DIR/.sessions.key` with restricted POSIX permissions (`0o600`).
2. **Tenant Isolation**: Sessions are segregated by tenant under `FBCHAT_STATE_DIR/sessions/{tenantId}/{sessionId}.enc`.
3. **Automatic Rehydration**: At container startup, valid encrypted sessions are loaded into memory with an initial status of `disconnected` until validated.
4. **Zero-Leakage Guarantee**: Credentials (cookies, appState, tokens) are never unencrypted on disk or exposed via any API route or log message.
5. **Secure Deletion**: Calling `DELETE /api/v1/sessions/{sessionId}` destroys both the in-memory session and the encrypted ciphertext file on disk.

## Global Webhook Dispatcher

The service includes an asynchronous webhook dispatcher providing:
- **Bounded FIFO Queue**: Default capacity of 1,000 events to prevent memory exhaustion under high load.
- **HMAC-SHA256 Signatures**: Included in the `X-Hub-Signature-256` header when a signing secret is configured.
- **SSRF Defense**: Automatically blocks webhook delivery to RFC 1918 private IPs, RFC 3927 link-local addresses, loopback, and multicast addresses. For controlled internal Docker networks, SSRF protection can be bypassed by setting `FBCHAT_ALLOW_INTERNAL_WEBHOOK=true`.
- **Exponential Backoff Retries**: Up to 3 attempts with exponential backoff on 5xx errors or network disconnects. Non-retryable 4xx client errors fail fast.
- **Telemetry & Metrics**: Track queue depth, delivered events, dropped events, failed deliveries, and last delivery timestamp via `/api/v1/diagnostics` and `/api/v1/webhook`.

## Capability Matrix

The endpoint `GET /api/v1/app/info` returns both a legacy flat capability list and an operational capability matrix with gate levels:
- `supported`: Production-ready, fully backed by verified provider methods.
- `experimental`: Backed by upstream methods but subject to Facebook anti-scraping or structure changes (e.g. Marketplace read/create).
- `unsupported`: Explicitly unsupported due to upstream limitations or safety requirements (e.g. marketplace update/delete, direct story creation).

## Media Staging & Boundary Model

Media management operates strictly behind a SocialManager-owned opaque identifier model:
1. **Opaque Identifiers**: Every uploaded or staged file is assigned a stable, cryptographically safe `mediaId` (`med_<uuid4_hex>`).
2. **Private Encapsulation**: Staged assets reside within the provider's private state boundary (`FBCHAT_STATE_DIR/media/{mediaId}/`).
3. **Zero-Leakage Guarantee**: Local filesystem paths, Facebook CDN URLs, internal hashes, and provider tokens are never exposed in public DTOs, WebSockets, or webhook payloads.
4. **Strict Safety Gates**:
   - Enforces a 25 MB file size limit per upload.
   - Restricts MIME types to an allowed whitelist (`image/*`, `audio/*`, `video/*`, `application/pdf`, `text/plain`, `application/zip`).
   - Automatically sanitizes original filenames to prevent path traversal.
   - Computes SHA-256 integrity checksums upon staging.
5. **Decoupled Dispatch**: Downstream consumers send attachments via `POST /api/v1/sessions/{sessionId}/messages/media` referencing only the `mediaId`. The provider resolves the local staging path internally and dispatches the payload to Facebook without leaking raw asset details.
