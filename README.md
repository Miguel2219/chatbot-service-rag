# chatbot-service-rag

RAG microservice built with Python and FastAPI. It ingests business documents,
turns them into embeddings with LangChain, stores them in ChromaDB, and answers
end-user questions through semantic search over that content.

Part of a four-service chatbot SaaS platform: a Spring Boot backend, an Angular
admin panel, an embeddable Preact widget, and this service.

## Why this exists

The platform separates data from inference. The Spring Boot backend owns tenant
data and configuration; this service owns everything that talks to the LLM.

The backend calls it to index a bot's documents and to answer incoming messages,
passing the tenant configuration with each request. Keeping the LLM layer in its
own service means the backend never needs to know about embeddings, prompts or
model providers — and this service can be scaled, redeployed or swapped to a
different model without touching the rest of the platform.

## Stack

- **Python** with **FastAPI** — REST API
- **LangChain** — document processing and embedding pipeline
- **ChromaDB** — vector store, running as an external service over HTTP
- **Cloudflare R2** — object storage for source documents
- **OpenAI** — text and vision models
- **pytest** — test suite

## Project structure

```
main.py            # FastAPI application entry point
config.py          # Environment-based configuration (Pydantic Settings)
dependencies.py    # Dependency injection
routers/           # API endpoints
schemas/           # Pydantic request/response models
services/          # Business logic
prompts/           # System prompt and operating rules
tests/             # pytest suite
```

Layered structure: routers stay thin, business logic lives in services, and
Pydantic schemas validate every request before it reaches the logic.

## API

The service is internal. Every endpoint is authenticated with a shared internal
API key and is meant to be called by the platform backend, not by end users.

| Method | Endpoint           | Description |
|--------|--------------------|-------------|
| POST   | `/chat`            | Answers a user message for a given bot, using semantic search over that tenant's documents and the conversation history. |
| POST   | `/process`         | Ingests a document, splits it, generates embeddings and stores them in the tenant's vector collection. |
| DELETE | `/delete-document` | Removes a document and its embeddings from the tenant's collection. |

## Design notes

**Stateless by design.** ChromaDB runs as a separate service reached over HTTP
instead of embedded, and source documents live in Cloudflare R2 instead of the
local filesystem. Restarting or redeploying the service does not lose indexed
documents or uploaded files — the container holds no durable state.

**Multi-tenant isolation.** Each bot's documents are indexed and queried
separately, so one tenant's content can never leak into another tenant's answers.

**Rate limiting on two axes.** Requests are limited per IP and per bot. The
per-bot limit matters more than the per-IP one here: it caps the cost a single
tenant can generate against the OpenAI API, independently of where the traffic
comes from.

**Resilience against the model provider.** Calls to OpenAI use explicit
timeouts — shorter for text, longer for vision, since image processing is slower —
plus a bounded retry count. A slow upstream degrades the response, it does not
hang the service.

**Bounded conversation memory.** Sessions expire on a TTL, the total number of
live sessions is capped, and a background task cleans up expired ones. History
sent to the model is truncated to a fixed number of turns, which keeps token
cost predictable instead of growing with conversation length.

## Prompt engineering

The system prompt (`prompts/default_rules.py`) defines a strict operating
contract for the model rather than a loose instruction:

- **Structured output** — every response is a JSON object with a field-level
  schema, including cross-field constraints (a captured lead must carry at least
  one contact method).
- **Prompt injection handling** — injection attempts are ignored and never
  acknowledged in the reply.
- **Explicit failure modes** — ten named mistakes the model must avoid. The most
  important: a lead is never registered without explicit user confirmation in
  that same message, so stated interest is not mistaken for consent.
- **Bounded autonomy** — the assistant may reason and calculate over the data in
  context (totals, discounts, opening hours, comparisons), but escalates to a
  human for executive actions such as placing orders or handling refunds.

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env    # fill in your own values
uvicorn main:app --reload
```

Interactive API docs at `http://localhost:8000/docs`.

Tests:

```bash
pip install -r requirements-dev.txt
pytest
```

## Configuration

All configuration is read from environment variables through Pydantic Settings.
See `.env.example` for the full list.

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | yes | OpenAI API credentials |
| `INTERNAL_API_KEY` | yes | Shared key used to authenticate calls from the platform backend |
| `CHROMA_HOST` | yes | Host of the ChromaDB service |
| `CHROMA_PORT` | no | ChromaDB port (default `8000`) |
| `R2_ACCESS_KEY_ID` | yes | Cloudflare R2 access key |
| `R2_SECRET_ACCESS_KEY` | yes | Cloudflare R2 secret key |
| `R2_ENDPOINT` | yes | Cloudflare R2 endpoint (`https://<account_id>.r2.cloudflarestorage.com`) |
| `R2_BUCKET` | yes | Bucket name — must match the one configured in the platform backend |
| `R2_ACCESS_KEY_ID` | yes | R2 access key |
| `R2_SECRET_ACCESS_KEY` | yes | R2 secret key |
| `R2_REGION` | no | Region (default `auto`, the R2 convention) |
| `MODEL_NAME` | no | Text model (default `gpt-4.1-mini`) |
| `VISION_MODEL_NAME` | no | Vision model (default `gpt-4o`) |
| `CHAT_HISTORY_MAX_TURNS` | no | Conversation turns kept in context (default `20`) |
| `SESSION_TTL_SECONDS` | no | Session lifetime (default `86400`) |
| `SESSION_MAX_COUNT` | no | Maximum concurrent sessions (default `2000`) |
| `SESSION_CLEANUP_INTERVAL_SECONDS` | no | Expired-session cleanup interval (default `300`) |
| `OPENAI_LLM_TIMEOUT_SECONDS` | no | Text model timeout (default `30`) |
| `OPENAI_VISION_TIMEOUT_SECONDS` | no | Vision model timeout (default `45`) |
| `OPENAI_MAX_RETRIES` | no | Retries on OpenAI failures (default `3`) |
| `RATE_LIMIT_CHAT_PER_IP` | no | Chat rate limit per IP (default `60/minute`) |
| `RATE_LIMIT_CHAT_PER_BOT` | no | Chat rate limit per bot (default `30/minute`) |
| `RATE_LIMIT_PROCESS_PER_IP` | no | Ingestion rate limit per IP (default `20/minute`) |


## Notes

This service was part of a larger platform I later stepped back from. Alongside
it I had built a custom admin panel, configuration layer and reporting — months
of work duplicating what existing tools like Chatwoot already solve. Recognizing
that led me to redesign the product around a leaner architecture, which became
Zolvion.