# API Reference

Base URL: `http://localhost:8000`

## Authentication

### POST /api/auth/signup
Register a new user.
```json
{ "name": "string", "email": "string", "password": "string" }
```
Response: `{ "token": "jwt...", "user": { "id": 1, "name": "...", "email": "..." } }`

### POST /api/auth/login
Login existing user.
```json
{ "email": "string", "password": "string" }
```
Response: `{ "token": "jwt...", "user": { "id": 1, "name": "...", "email": "..." } }`

### GET /api/auth/me
Get current user info. Requires Bearer token.
Response: `{ "id": 1, "name": "...", "email": "..." }`

## Chat

### POST /api/chat
Main query endpoint. Auth optional (guest session if no token).
```json
{
  "message": "string",
  "session_id": "string (uuid)",
  "mode": "auto|knowledge|analysis|document|pathfinder|scrutiny",
  "force_mode": "string",
  "conv_id": "int (optional, for authenticated users)"
}
```
Response includes: `response`, `mode`, `meta` (remapped_laws, urgency_flags, limitation_days, jurisdiction, citations, confidence, document_ready, etc.)

### POST /api/upload
Contract evaluation endpoint. Multipart form-data.
- Field `file`: PDF, DOCX, or TXT (max 50MB)
- Field `session_id`: string

Response: `{ "evaluation": { "overall_score", "risk_level", "clauses", "summary", "recommendations" }, "session_id": "..." }`

### GET /api/document/{session_id}
Download generated .docx file. Returns file as attachment.

### DELETE /api/history/{session_id}
Clear chat history for a session.

### DELETE /api/draft/state/{session_id}
Cancel drafting interview, reset state.

### GET /api/health
Health check. Returns `{ "status": "healthy" }`

## Conversations (Requires Bearer Token)

### GET /api/conversations
List conversations (paginated).
Query params: `page` (default 1), `per_page` (default 20)
```json
{
  "conversations": [
    { "id": 1, "title": "...", "created_at": "...", "updated_at": "...", "message_count": 5 }
  ],
  "total": 10,
  "page": 1,
  "per_page": 20
}
```

### POST /api/conversations
Create new conversation.
```json
{ "title": "string (optional)" }
```
Response: `{ "id": 2, "title": "...", "created_at": "..." }`

### GET /api/conversations/{id}
Load conversation with all messages.
```json
{
  "id": 1,
  "title": "...",
  "messages": [
    { "id": 1, "role": "user|assistant", "content": "...", "meta": {}, "created_at": "..." }
  ]
}
```

### DELETE /api/conversations/{id}
Delete conversation and its messages.

### POST /api/conversations/migrate
Bulk-import guest session messages (for session takeover on login).
```json
{
  "turns": [
    { "role": "user|assistant", "content": "string", "meta": {} }
  ],
  "title": "string (optional)"
}
```
Response: `{ "conversation_id": 3, "imported_count": 10 }`

## Request Flow (for /api/chat)

1. Auth resolution (JWT or guest)
2. Conversation resolution (map session_id to conv_id)
3. Message persistence (to SQLite if authenticated)
4. Interview state check (drafting in progress?)
5. Interruption guard (clarification/hypothetical/pushback)
6. Crisis pre-check (self-harm, violence, confinement → helplines)
7. Jurisdiction gate (non-Indian → rejected)
8. Direct legal query patterns (15 regex patterns → force knowledge mode)
9. Triage LLM call (classify: off-topic / direct legal / educational / document / grievance)
10. State machine routing (3-phase flow or pass-through)
11. Pipeline dispatch (6-layer RAG fallthrough)
12. Response construction (widget metadata)
13. Response persistence (conv_id injected for frontend)
