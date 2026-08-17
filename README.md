# AI Sales Agent

Production-oriented AI Sales Agent that replaces the first line of sales.

It independently guides a prospect through the sales funnel: detects intent, answers company questions using a knowledge base, qualifies the lead, scores it, and books a discovery call.

> **Why this is an agent, not a chatbot:** the LLM does not just reply to messages. It analyzes pipeline state, decides the next best action, calls external tools (CRM, calendar, RAG), updates state in external systems, and drives the user toward a business goal — a booked meeting with a qualified lead.

---

## Table of contents

- [Business problem](#business-problem)
- [Demo conversation](#demo-conversation)
- [Architecture](#architecture)
- [Agent workflow](#agent-workflow)
- [Tech stack](#tech-stack)
- [Key features](#key-features)
- [Project structure](#project-structure)
- [Installation](#installation)
- [Environment variables](#environment-variables)
- [Run locally](#run-locally)
- [Run with Docker](#run-with-docker)
- [API](#api)
- [Tests](#tests)
- [Future improvements](#future-improvements)

---

## Business problem

Most incoming leads are lost because:

- response time is too long;
- sales reps spend hours on low-intent inquiries;
- qualification data is scattered across messengers and CRMs;
- no one follows up consistently.

**AI Sales Agent** solves this by:

- instantly responding to incoming messages;
- qualifying prospects naturally, one question at a time;
- calculating a lead score and offering a meeting only when the lead is hot;
- booking the meeting directly into the calendar;
- syncing everything to a mock CRM with full audit history.

---

## Demo conversation

A dental clinic chain reaches out.

| User | Agent |
|---|---|
| Привет. У нас сеть стоматологий. Хотим автоматизировать обработку заявок. | Понял. Откуда сейчас в основном приходят заявки — сайт, Telegram, WhatsApp или другие каналы? |
| WhatsApp и сайт. Около 1500 в месяц. | Спасибо. А какую CRM или систему для учёта заявок используете сейчас? |
| Bitrix24 | Понятно. Какой бюджет вы рассматриваете на внедрение? |
| Бюджет 50k+ | Понял. Принимаете ли вы финальное решение по такому проекту? |
| Да, я директор | С вашим объёмом обращений такой сценарий имеет смысл детально посчитать. Могу предложить несколько свободных слотов для 30-минутного созвона. |
| давайте | Вот несколько ближайших слотов. Выберите удобное время: (slots) |
| 2026-08-17T12:00:00+03:00 | Отлично, встреча забронирована. Скоро пришлю подтверждение на почту. |

Behind the scenes the agent:

1. Detects `new_lead` intent.
2. Saves `business_problem`, `channels`, `monthly_leads`, `current_software`, `budget_range`, `urgency`, `decision_maker`.
3. Recalculates lead score (80 → `qualified`).
4. Calls `get_available_slots`.
5. Calls `book_meeting` and moves the lead to `meeting_booked`.

All actions are visible in the demo dashboard.

---

## Architecture

```mermaid
graph LR
    A[User message] --> B[FastAPI /chat]
    B --> C[SalesAgent]
    C --> D[(PostgreSQL<br/>leads + events)]
    C --> E[Redis<br/>short-term memory]
    C --> F[LLM Provider<br/>OpenAI / Anthropic / Mock]
    C --> G[Tool Registry]
    G --> H[CRM tools]
    G --> I[Calendar tools]
    G --> J[RAG tools]
    J --> K[Qdrant / ChromaDB]
    K --> L[Knowledge Base]
    C --> M[Demo Dashboard]
```

### Design decisions

| Decision | Why |
|---|---|
| **Two-step LLM loop** | Decision call produces structured `AgentDecision`; response call generates natural text with RAG/tool context. Separating the two makes the backend deterministic and testable. |
| **Provider-agnostic LLM layer** | `LLMProvider` protocol lets you swap OpenAI, Anthropic, or a mock provider via env var. |
| **Tool registry with Pydantic schemas** | Every tool declares its input/output schema. The registry validates arguments, logs calls, and handles errors in one place. |
| **Mock CRM as a service layer** | All lead mutations write audit events. Replacing it with a real CRM requires only a new adapter. |
| **RAG with metadata filtering** | Company knowledge lives in markdown files, not in the system prompt. The agent retrieves only relevant chunks with source attribution. |
| **Configurable lead scoring** | Scoring weights and thresholds live in `config/scoring.yaml`; no code changes needed to tune them. |
| **Redis short-term + PG long-term memory** | Conversation history is cheap and fast; structured lead data survives restarts. |

---

## Agent workflow

```text
Receive message
    ↓
Load conversation + lead state
    ↓
LLM structured decision (intent, stage, tool, memory_updates, next_best_action)
    ↓
Apply memory updates to lead profile
    ↓
Validate and apply stage transition
    ↓
Call tool if required (CRM / calendar / RAG / scoring)
    ↓
Recalculate lead score if needed
    ↓
Generate final response (with RAG context and tool results)
    ↓
Persist messages and final state
    ↓
Return AgentState to dashboard
```

---

## Tech stack

- **Python 3.12**
- **FastAPI** + **Uvicorn**
- **Pydantic** + **Pydantic Settings**
- **SQLAlchemy 2.0** (async) + **Alembic**
- **PostgreSQL**
- **Redis**
- **Qdrant** (vector DB) with ChromaDB as a local alternative
- **OpenAI / Anthropic** LLM providers
- **Structlog** for structured observability
- **Docker** + **Docker Compose**
- **Pytest** for testing

---

## Key features

- **Intent detection**: greeting, service/pricing/case/technical questions, new lead, qualification answers, meeting requests, objections, not interested, etc.
- **Natural qualification**: one question at a time, context-aware, no interrogation.
- **RAG pipeline**: query preprocessing → embedding → vector search → top-K chunks → LLM answer. No hallucinated prices or cases.
- **Tool calling**: `search_knowledge_base`, `create_lead`, `update_lead`, `get_lead`, `calculate_lead_score`, `get_available_slots`, `book_meeting`, `save_memory`.
- **Lead scoring**: 0–100 score with configurable weights and explicit reasons.
- **State machine**: `new → engaged → qualification → qualified → meeting_proposed → meeting_booked` plus terminal states.
- **Memory**: Redis ring buffer for conversation history; PostgreSQL for long-term lead profile.
- **Observability**: JSON logs with `conversation_id`, `lead_id`, intent, tool name, latency, errors.
- **Resilience**: failures in LLM, RAG, CRM, or calendar degrade gracefully instead of breaking the conversation.

---

## Project structure

```text
ai-sales-agent/
├── app/
│   ├── agent/            # agent loop, prompts, schemas, state machine
│   ├── api/              # FastAPI routes
│   ├── core/             # config, logging, database, exceptions
│   ├── memory/           # short-term (Redis) and long-term (PG) memory
│   ├── models/           # SQLAlchemy models
│   ├── rag/              # embeddings, ingestion, retrieval, vector stores
│   ├── services/         # CRM, calendar, LLM providers
│   └── tools/            # tool registry and tool implementations
├── alembic/              # database migrations
├── config/
│   └── scoring.yaml      # configurable lead scoring
├── knowledge_base/       # markdown documents for RAG
├── frontend/             # demo dashboard (HTML + JS)
├── tests/
│   ├── unit/             # scoring, CRM, calendar, state machine
│   └── integration/      # API + end-to-end demo scenario
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Installation

### Clone and create a virtual environment

```bash
git clone <repo-url>
cd ai-sales-agent
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Set up environment variables

```bash
cp .env.example .env
# edit .env with your keys
```

### Create the database

```bash
# For local SQLite (no Postgres needed):
export DATABASE_URL="sqlite+aiosqlite:///./test.db"
alembic upgrade head

# Or start Postgres/Redis/Qdrant and use the URL from .env.
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/sales_agent` | Async SQLAlchemy DB URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Short-term memory |
| `QDRANT_URL` | `http://localhost:6333` | Vector database |
| `QDRANT_API_KEY` | — | Required for Qdrant in Docker Compose |
| `QDRANT_COLLECTION_NAME` | `sales_agent_kb` | Collection for RAG |
| `SECRET_KEY` | — | JWT secret; must be at least 32 characters in production |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT lifetime |
| `OPENAI_API_KEY` | — | Required when `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=anthropic` |
| `LLM_PROVIDER` | `openai` | `openai` / `anthropic` / `mock` |
| `LLM_MODEL` | `gpt-4o-mini` | Model name |
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `keyword` (fallback) |
| `VECTOR_STORE_PROVIDER` | `qdrant` | `qdrant` or `chroma` |
| `POSTGRES_PASSWORD` | — | Docker Compose PostgreSQL password |
| `REDIS_PASSWORD` | — | Docker Compose Redis password |

---

## Run locally

```bash
export LLM_PROVIDER=mock            # run without API keys for demo
export EMBEDDING_PROVIDER=keyword   # use keyword fallback for RAG
export DATABASE_URL=sqlite+aiosqlite:///./test.db

uvicorn app.main:app --reload
```

Open:

- Chat + Agent State dashboard: http://localhost:8000/
- Leads dashboard: http://localhost:8000/leads.html
- API docs: http://localhost:8000/api/docs (development only)

The public chat widget automatically requests an anonymous token from `/api/v1/auth/public-token`. The leads dashboard requires an operator/admin JWT from `/api/v1/auth/token`.

To use a real LLM, set `LLM_PROVIDER=openai` and provide `OPENAI_API_KEY`. In production set a strong `SECRET_KEY` and never expose PostgreSQL/Redis/Qdrant ports.

---

## Run with Docker

```bash
export OPENAI_API_KEY=sk-...
export LLM_PROVIDER=mock
export POSTGRES_PASSWORD=change-me
export REDIS_PASSWORD=change-me
export QDRANT_API_KEY=change-me
export SECRET_KEY=change-me-in-production-min-32-characters-long
docker compose up --build
```

The compose stack starts PostgreSQL, Redis, Qdrant, and the FastAPI backend on an internal network. Only the backend port `8000` is published; data stores are not reachable from the host.

---

## API

All business endpoints are under `/api/v1` and require a Bearer JWT, except `/api/v1/chat` which also accepts an anonymous public token and `/health` which is open.

### Authentication

```bash
# Public chat token (anonymous, chat scope only)
curl -X POST http://localhost:8000/api/v1/auth/public-token

# Operator/admin token (requires seeded user)
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email": "operator@example.com", "password": "..."}'
```

### `POST /api/v1/chat`

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"conversation_id": "conv_001", "message": "Хотим автоматизировать обработку заявок"}'
```

Response:

```json
{
  "conversation_id": "conv_001",
  "lead_id": "lead_...",
  "intent": "new_lead",
  "stage": "qualification",
  "lead_score": 42,
  "lead_quality": "potential",
  "next_best_action": "ask_channel",
  "missing_fields": ["channels", "monthly_leads"],
  "collected_fields": { "business_problem": "..." },
  "last_tool_calls": [...],
  "response": "Понял. Откуда сейчас в основном приходят заявки?"
}
```

### Other endpoints

- `GET /api/v1/leads` — list leads (operator/admin)
- `GET /api/v1/leads/{lead_id}` — lead detail (operator/admin)
- `PATCH /api/v1/leads/{lead_id}` — update allowed lead fields (operator/admin)
- `GET /api/v1/leads/{lead_id}/events` — audit timeline (operator/admin)
- `GET /api/v1/conversations/{conversation_id}` — message history (authenticated)
- `GET /health` — liveness/readiness check

---

## Tests

```bash
pytest -q
```

The suite covers:

- lead scoring logic;
- deterministic stage policy and meeting eligibility;
- tenant-aware CRM create/update/dedup with audit events;
- calendar slot generation, overlap rejection and double-booking protection;
- the full dental-chain demo conversation via the API;
- security regression: anonymous access, IDOR/tenant isolation, mass-assignment rejection, XSS and security headers.

CI gates (`.github/workflows/ci.yml`) run ruff, mypy, Alembic check, pytest and bandit against PostgreSQL, Redis and Qdrant.

---

## Future improvements

- Add real OAuth / API integrations for Google Calendar, Calendly, HubSpot, Bitrix24.
- Implement human handoff with live agent notifications.
- Add conversation analytics dashboard (conversion rate, average lead score, bottlenecks).
- Fine-tune a small model for intent detection to reduce LLM costs.
- Add multi-language support with per-language RAG collections.
- Voice and WhatsApp Business API channels.

---

## License

MIT
