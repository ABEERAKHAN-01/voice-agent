# Voice AI Patient Registration

A voice-based patient intake agent (Vapi + Twilio + OpenAI) backed by a FastAPI /
PostgreSQL / Redis service. Call the number, register a patient by talking naturally,
call back later and the record is still there.

For deployment steps, see **[INSTRUCTIONS.md](./INSTRUCTIONS.md)**.

## Architecture

```
Caller --(PSTN)--> Twilio number --> Vapi (STT: Deepgram, LLM: OpenAI gpt-4o,
TTS: 11labs) --tool calls (HTTPS webhook)--> FastAPI (/vapi/webhook)
                                                    |
                                     Service layer (business logic, caching)
                                                    |
                                     Repository layer (SQLAlchemy 2.0, async)
                                                    |
                                      PostgreSQL (patients table)   Redis (cache)

Separately: REST API (/patients ...) for querying/managing records directly.
```

**Separation of concerns**
- `app/vapi/` — prompt + tool schemas (the "conversation contract" with the LLM), version
  controlled instead of living only in the Vapi dashboard.
- `app/api/vapi_webhook.py` — telephony/LLM integration boundary. Translates Vapi's
  tool-call payloads into calls on the same service layer the REST API uses.
- `app/api/patients.py` — REST API, thin controllers only.
- `app/services/` — business logic: validation orchestration, duplicate detection,
  cache invalidation. This is the one place both entry points (phone call, REST) share.
- `app/repositories/` — the only layer that touches SQLAlchemy/SQL.
- `app/models/`, `app/schemas/` — ORM model vs. Pydantic v2 API contract, kept separate
  on purpose so API validation isn't silently coupled to DB column definitions.

## Tech stack & why

| Layer | Choice | Why |
|---|---|---|
| Telephony + Voice | Vapi (native number; Twilio import optional) | Vapi issues a free dialable US number directly — no separate telephony account needed. Twilio is only used if you need a non-US number or want to keep a number you already own. |
| LLM | OpenAI gpt-4o | Strong instruction-following for a conversational, correction-tolerant flow. |
| Backend | FastAPI | Async-native (matches async SQLAlchemy + Redis), automatic OpenAPI docs, Pydantic v2 built in. |
| ORM | SQLAlchemy 2.0 (async, typed `Mapped[]`) | Modern typed models, async engine fits FastAPI's event loop. |
| Validation | Pydantic v2 | Server-side validation independent of whatever the voice agent already checked — spec requirement. |
| Database | PostgreSQL | Real constraints/types, durable persistence across restarts (spec requirement). |
| Cache | Redis | Cache-aside for hot reads during a live call (phone-number duplicate lookups, patient-by-id) — keeps webhook latency low so the caller doesn't hear dead air. |
| Architecture | Service + Repository | Lets the phone-call path and REST path share one business-logic layer without duplicating validation/caching logic. |
| Observability | Langfuse + structlog | Langfuse traces each tool call end-to-end (arguments in, DB result out); structlog gives JSON logs to stdout per the spec's logging requirement. |
| Deployment | Railway | One Postgres + one Redis + one web service, Dockerfile-based, fast to stand up. |

## Environment variables

See `.env.example`. Required at minimum: `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`,
`VAPI_API_KEY`, `VAPI_WEBHOOK_SECRET`, `VAPI_SERVER_URL`. Twilio vars are only needed if
`USE_TWILIO_IMPORT=true` (non-US number, or porting a number you already own) — by
default the setup script provisions a free US number directly from Vapi.
`LANGFUSE_*` is optional — tracing no-ops if unset.

## Running locally

```bash
cp .env.example .env   # fill in values
docker compose up -d postgres redis
pip install -r requirements.txt
uvicorn app.main:app --reload
python scripts/seed.py           # optional demo data
pytest                           # runs against in-memory SQLite
```

Expose locally with `ngrok http 8000` and point `VAPI_SERVER_URL` at the ngrok HTTPS URL
+ `/vapi/webhook` while developing the voice agent against your laptop.

## Known limitations / trade-offs

- **`Base.metadata.create_all()` instead of Alembic migrations.** Fast to deploy; the
  trade-off documented per the spec's "know when to use a shortcut" guidance. A real
  production system would use Alembic for versioned schema changes.
- **No auth on the REST API.** The webhook is protected by a shared secret header; the
  `/patients` CRUD endpoints are open, matching the assessment's non-HIPAA, non-production
  scope. Would add API-key or OAuth2 auth next.
- **Duplicate detection is phone-number-only.** Good enough for the bonus requirement;
  a production system would also fuzzy-match name + DOB to catch a caller phoning from a
  different number.
- **Multi-language, appointment scheduling, call recording** are not implemented (listed
  as bonus/optional in the spec). `preferred_language` is captured as a field; the
  assistant is not yet instructed to actually converse in Spanish.
- **Redis cache TTL is short (60s) and best-effort** — a cache failure always falls back
  to Postgres rather than breaking the request.

## Next steps (if continuing)

- Alembic migrations.
- Fuzzy duplicate matching (name + DOB) in addition to phone number.
- Spanish-language conversation branch ("Hablo español" → switch assistant language).
- Simple read-only dashboard (`GET /patients` rendered as an HTML table) for the bonus
  "Dashboard" item.
- API key auth on `/patients/*`.
