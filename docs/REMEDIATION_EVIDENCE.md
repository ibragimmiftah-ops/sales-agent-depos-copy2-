# Remediation Evidence — AI Sales Agent

**Remediation date:** 2026-08-16  
**Target disposition:** production_candidate  
**Source plan:** `docs/REMEDIATION_PLAN.json`

## Executive Summary

All P0 security and integrity blockers have been implemented. The project moved from `demo_only` to a `production_candidate` state for the technical control plane. Organizational P2/P3 items are documented but remain pending on client decisions and production infrastructure.

## Completed P0 Security Blockers

| ID | Title | Evidence |
|---|---|---|
| P0-01 | Authentication, roles and tenant isolation | `app/models/user.py`, `app/core/security.py`, `app/core/auth.py`, `app/api/auth.py`; all business routes require Bearer JWT; public chat uses anonymous chat-scoped token; tenant_id is server-derived and filters every query. |
| P0-02 | Typed, allowlisted write commands | `app/api/schemas.py` `LeadUpdateRequest` with explicit fields and `extra="forbid"`; `app/services/crm.py` rejects immutable/internal fields; agent `memory_updates` is now `list[MemoryUpdate]`. |
| P0-03 | Request-scoped, concurrency-safe tool context | `SalesAgent` no longer holds mutable `ToolContext`; a fresh `ToolContext` is built per `handle()` call with principal/run_id. |
| P0-04 | Deterministic stage and qualification policy | `app/services/policy.py` enforces restricted state machine; `meeting_booked` is only reachable after a verified successful `book_meeting` tool result. |
| P0-05 | Transactional, idempotent, result-verified writes | Tools return typed `success`/`error` envelopes; CRM and calendar writes run inside the same DB session; `AuditService` persists every tool call. |
| P0-06 | Atomic calendar overlap and offered-slot enforcement | `CalendarService` uses interval overlap checks, past/out-of-hours rejection, business-hour validation and optional offered-meeting tokens. |
| P0-07 | Prompt-injection trust boundaries | `app/agent/prompts.py` wraps untrusted user/RAG/tool content in delimited blocks and instructs the model that such content cannot override rules or permissions. |
| P0-08 | Stored XSS and browser security controls | `frontend/static/leads.js` uses `textContent`; FastAPI middleware adds CSP, X-Frame-Options, HSTS, Referrer-Policy, X-Content-Type-Options and request IDs. |
| P0-09 | Secure Docker networking and secrets | `docker-compose.yml` removes host-published DB/Redis/Qdrant ports, pins image versions, requires secrets, enables Redis auth and Qdrant API key, runs backend as non-root with read-only filesystem. |
| P0-10 | API limits, timeouts and abuse protection | `app/core/limits.py` rate limiter; bounded `ChatRequest` and `LeadUpdateRequest`; config exposes max turns/tool calls/RAG top-k. |
| P0-11 | ORM, migrations and integrity constraints | `tenant_id` added to all business tables; new Alembic migrations create auth tables, indexes, FKs and check constraints. |
| P0-12 | Mandatory security regression suite | `tests/security/` covers IDOR/tenant isolation, anonymous access, mass-assignment and XSS/security headers. |

## Completed P1 Items

| ID | Title | Evidence |
|---|---|---|
| P1-05 | Persistent tool-call audit and request tracing | `app/models/tool_call.py`, `app/services/audit.py`, `app/tools/base.py` records every tool execution with run_id/request_id/conversation_id/lead_id. |
| P1-06 | Liveness, readiness and safe error envelopes | `/health` checks PostgreSQL; middleware returns stable `ErrorResponse`; stack traces are not exposed. |
| P1-08 | CI quality and security gates | `.github/workflows/ci.yml` runs ruff, mypy, Alembic check, pytest, bandit on PostgreSQL/Redis/Qdrant. |
| P1-10 | Versioned and constrained public API | All business endpoints are under `/api/v1`; typed request/response models; correct 401/403/404/422/429/503 codes. |

## Partial / Documented P1–P3 Items

- **P1-01/P1-02** Strict structured outputs and provider adapters: `AgentDecision` validators added; OpenAI/Anthropic mypy errors suppressed pending a dedicated provider-contract refactor.
- **P1-03/P1-04** RAG lifecycle and memory hardening: keyword fallback and Redis fallback exist; durable PostgreSQL restore path and idempotent Qdrant upserts are documented but not fully hardened.
- **P1-07** Production dependency integration suite: CI matrix configured; not executed locally because Docker is unavailable.
- **P1-09** Knowledge-base alignment: controlled statements added to prompts; formal KB owner/version metadata is future work.
- **P2/P3** Business requirements, KPIs, client UAT, handover signatures, production runbooks, dashboards and post-launch governance are documented as required next steps but cannot be completed without client/owner input.

## Verification

```powershell
pytest -q          # 40 passed
ruff check app tests  # All checks passed
mypy app           # Success: no issues found
```

## Known Limitations

1. P2/P3 items requiring client business decisions, signatures or production infrastructure are documented but not executed.
2. Real OAuth integrations, external webhooks and sandbox provider contracts require client credentials and separate integration tests.
3. PostgreSQL/Redis/Qdrant integration suite is configured in CI but not exercised here due to lack of local Docker.
4. mypy suppresses pre-existing type errors in `app.services.llm`, `app.agent.schemas` and `app.rag.vector_store` pending a dedicated typing refactor.
