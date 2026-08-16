# Independent Audit Report — NovaFlow AI Sales Agent

**Audit date:** 2026-08-16  
**Scope:** full repository (`app`, database models/migrations, agent loop, tools, RAG, memory, API, frontend, tests, Docker and documentation)  
**Method:** independent static review by four parallel reviewers, evidence reconciliation, Git inspection and execution of the existing test suite.

## Executive Verdict

The repository is a functional **portfolio/demo prototype**, but it is **not production-ready and must not be exposed to untrusted users or client data** in its current state.

The implementation demonstrates useful agentic concepts:

- structured `AgentDecision` output;
- explicit tool registry;
- CRM and calendar side effects;
- deterministic lead scoring;
- state machine;
- RAG abstractions;
- Redis/PostgreSQL memory split;
- FastAPI and a transparent demo dashboard.

However, the current security and business-control boundaries allow anonymous access to PII, cross-lead writes, prompt-injection-assisted tool execution, inconsistent booking state and request cross-contamination under concurrency.

**Production readiness:** blocked.  
**Client UAT readiness:** blocked until P0 items in `docs/REMEDIATION_PLAN.json` are complete.  
**Demo readiness:** acceptable only on an isolated local machine with synthetic data and `LLM_PROVIDER=mock`.

## Verification Baseline

- Git repository exists with eight implementation commits.
- Existing test suite: **19 passed in 5.08s**.
- Tracked secret check: only `.env.example` is tracked; `.env` and `*.db` are ignored.
- Existing tests use SQLite, mock LLM and keyword retrieval; they are not production-integration evidence.
- Docker could not be executed in this workstation environment because Docker is unavailable.

Passing tests do not invalidate the findings below: the suite does not test authentication, authorization, tenant isolation, concurrency, prompt injection, real Qdrant/PostgreSQL/Redis, provider contracts or production failure paths.

## Critical Findings

### C1. Anonymous PII access, arbitrary writes and conversation takeover

There is no authentication, authorization or ownership check on business endpoints. An anonymous caller can enumerate leads, read contact and qualification data, patch any lead, read full conversations and continue another conversation by supplying its ID.

Evidence:

- `app/main.py:38-41`
- `app/api/chat.py:18-25`
- `app/api/leads.py:20-68`
- `app/api/conversations.py:17-36`
- `app/api/schemas.py:10-19`

Impact:

- complete confidentiality and integrity loss for lead PII;
- IDOR across conversations and leads;
- unauthenticated CRM administrator capability.

Required control: authenticated principal, tenant/ownership-bound queries, separate public-chat and operator/admin permissions.

### C2. LLM and public API can mutate arbitrary lead fields and target another lead

`PATCH /leads/{id}` accepts `dict[str, Any]`. The CRM service writes every attribute present on the ORM model rather than an explicit allowlist. LLM `memory_updates` is also unrestricted. For tool calls, an LLM-provided `lead_id` is preserved instead of being replaced with the current server-side lead.

Evidence:

- `app/api/schemas.py:18-19`
- `app/services/crm.py:137-168`
- `app/agent/schemas.py:95-98`
- `app/agent/agent.py:281-323`
- `app/tools/crm.py:79-109`

Potentially writable internal fields include `id`, `conversation_id`, `status`, `lead_score`, timestamps and meeting state.

Required control: typed role-specific patch schemas, immutable-field rejection and unconditional server-side binding of tenant/conversation/lead identifiers.

### C3. Concurrent requests share mutable SQLAlchemy session state

The process-wide `SalesAgent` singleton stores one mutable `ToolContext`. Every request overwrites `self.tool_context.session`, including around awaited tool operations.

Evidence:

- `app/agent/agent.py:41-49`
- `app/agent/agent.py:137-140`
- `app/agent/agent.py:177-184`
- `app/agent/agent.py:359-366`
- `app/tools/calendar.py:54-69`
- `app/tools/scoring.py:178-198`

Impact: request A can continue on request B's session, causing cross-conversation writes, transaction corruption and data leakage.

Required control: construct an immutable request-scoped `ToolContext` inside every `handle()` call.

### C4. Persistent and indirect prompt injection reaches the system role

User-derived lead fields are interpolated into the system prompt. RAG chunks and tool results are also concatenated into a system message without a strong untrusted-data boundary.

Evidence:

- `app/agent/prompts.py:78-116`
- `app/agent/prompts.py:120-146`
- `app/rag/retrieval.py:44-52`

Impact: text saved as a business problem or inserted into Qdrant can act as persistent instructions and influence later tool decisions.

Required control: keep untrusted content in delimited data messages, add explicit non-instruction policy, sanitize provenance and enforce all write permissions outside the LLM.

### C5. PostgreSQL, Redis and Qdrant are exposed with unsafe defaults

Compose publishes all data-store ports. PostgreSQL uses `postgres/postgres`; Redis and Qdrant have no configured authentication.

Evidence:

- `docker-compose.yml:4-18`
- `docker-compose.yml:20-35`

Impact: direct database, memory and knowledge-base compromise when host ports are reachable.

Required control: internal Docker network only, generated secrets, service authentication, TLS where traffic crosses hosts and a production secret manager.

### C6. Stored XSS in the leads dashboard

User/LLM-controlled lead values are interpolated into `innerHTML`.

Evidence:

- `frontend/static/leads.js:14-24`
- safe contrast: `frontend/static/app.js:13-18`

Impact: arbitrary same-origin JavaScript execution when an operator opens the leads page.

Required control: create DOM nodes and assign `textContent`; add Content Security Policy and security headers.

## High Findings

### H1. Qualification and meeting eligibility are advisory, not deterministic

The LLM-selected stage is applied before scoring and the state machine allows forward jumps to qualified/booked states. `should_offer_meeting` is not enforced by backend policy.

Evidence:

- `app/agent/agent.py:106-125`
- `app/agent/agent.py:174-193`
- `app/agent/state.py:11-46`
- `app/agent/schemas.py:111-114`
- `app/agent/prompts.py:20-29`

Required control: backend qualification policy must calculate the allowed transition from verified score, required fields, contact state and successful tool result.

### H2. Failed tools can still produce success claims and inconsistent state

The registry converts exceptions into ordinary dictionaries. The agent logs the tool as executed and may return the LLM's optimistic draft. Stage changes occur before tool execution.

Evidence:

- `app/tools/base.py:74-93`
- `app/agent/agent.py:106-159`
- `app/agent/agent.py:198-238`
- `app/services/llm.py:397-414`

Required control: typed success/error result, rollback/savepoint on failure, state transition only after verified side effect and deterministic failure response.

### H3. Calendar integrity and idempotency are insufficient

Calendar checks compare exact start timestamps, not intervals. Check-then-insert is race-prone; there is no database uniqueness/exclusion constraint, idempotency key, offered-slot token, business-hour validation or future-time check.

Evidence:

- `app/services/calendar.py:54-84`
- `app/services/calendar.py:95-159`
- `app/models/meeting.py:22-38`
- `alembic/versions/2026_08_15_initial_schema.py:73-85`

Required control: PostgreSQL interval/exclusion constraint, atomic booking transaction, signed/persisted pending action and idempotency key.

### H4. Anthropic path and provider fallback are broken

Anthropic receives system-role messages in the messages list while also using a top-level system value, and inherits the OpenAI default model. Missing API keys fail during singleton construction before degraded-mode fallback can run.

Evidence:

- `app/agent/prompts.py:104-146`
- `app/services/llm.py:136-193`
- `app/core/config.py:32-38`
- `app/agent/agent.py:41-44`

Required control: provider-specific message adapters and model settings, startup validation, contract tests and a safe fallback factory.

### H5. Structured output is JSON mode, not strict schema enforcement

OpenAI uses JSON mode. `ValidationError` is not retried/repaired. Cross-field invariants are absent, so dangerous combinations remain valid.

Evidence:

- `app/services/llm.py:68-97`
- `app/agent/schemas.py:70-118`

Examples currently accepted:

- `stage=meeting_booked` without a successful booking;
- `tool=book_meeting` for an arbitrary `lead_id`;
- `needs_rag=true` without a useful query;
- internal fields in `memory_updates`.

### H6. Keyword RAG startup does not populate the store used by the agent

Startup ingestion creates a fresh in-memory store, while the agent retriever creates another. Qdrant IDs such as `pricing_0` are not valid UUID/integer point IDs.

Evidence:

- `app/rag/ingestion.py:53-75`
- `app/rag/retrieval.py:18-20`
- `app/rag/vector_store.py:92-104`
- `app/rag/vector_store.py:251-260`

Existing pricing tests pass because mock responses are canned, not because retrieval was proven.

### H7. Redis degradation and durable-memory recovery are incomplete

Only initial Redis connection is guarded. Runtime Redis operation failures are not. Once unavailable, Redis is never retried. PostgreSQL messages are persisted but never used to recover history.

Evidence:

- `app/memory/short_term.py:28-89`
- `app/agent/agent.py:69-78`
- `app/agent/agent.py:215-238`

### H8. ORM and Alembic migration differ

The ORM declares `conversations.lead_id` as a foreign key, but the migration does not create that FK. Tests use `Base.metadata.create_all`, so migration drift is not detected.

Evidence:

- `app/models/conversation.py:25-30`
- `alembic/versions/2026_08_15_initial_schema.py:21-29`
- `tests/conftest.py:28-50`

There are also redundant bidirectional FK columns (`leads.conversation_id` and `conversations.lead_id`) that can disagree.

### H9. No authentication, tenant isolation, rate limiting or resource bounds

There is no tenant model, authorization dependency, API rate limit, LLM/tool timeout, message length limit, bounded calendar range or bounded lead pagination.

Evidence:

- `app/models/lead.py:43-104`
- `app/models/conversation.py:22-59`
- `app/api/schemas.py:10-19`
- `app/api/leads.py:20-27`
- `app/tools/calendar.py:15-19`
- `app/main.py:32-52`

### H10. Health endpoint is a false positive

`GET /health` always returns `ok` without checking PostgreSQL, Redis, Qdrant or the configured LLM.

Evidence:

- `app/api/health.py:10-12`
- `app/api/schemas.py:22-25`

### H11. Client-facing security and handoff claims exceed implementation

The knowledge base claims RBAC, encryption, human handoff and a 12-month retention policy, while the code has no RBAC, handoff workflow or retention job.

Evidence:

- `knowledge_base/faq.md:19-29`
- `knowledge_base/technical_capabilities.md:20-43`
- `README.md:328-335`

These statements must be corrected or implemented before customer use.

### H12. No formal eval, security or production-integration suite exists

`tests/eval` is empty. Current integration tests use SQLite, mock LLM and keyword retrieval. There are no tests for authorization, IDOR, prompt injection, concurrency, provider contracts, real Qdrant/PostgreSQL/Redis or migration drift.

Evidence:

- `tests/eval/__init__.py`
- `tests/conftest.py:17-21`
- `tests/integration/test_chat.py:9-51`

## Medium Findings

1. The current user message is duplicated in decision/response prompts (`app/agent/agent.py:69-78`, `app/agent/prompts.py:111-117`).
2. Lead summaries omit known fields such as email, phone, urgency and deadline (`app/agent/prompts.py:78-101`).
3. Tool output schemas are declared but never validated (`app/tools/base.py:30-40`, `app/tools/base.py:74-84`).
4. Only the final tool result reaches response generation (`app/agent/agent.py:199-206`).
5. RAG has no relevance threshold, context budget or trusted provenance (`app/rag/retrieval.py:44-52`).
6. Any nonempty unrecognized budget is scored as suitable (`app/tools/scoring.py:99-109`).
7. Mock mode fabricates urgency from a budget message (`app/services/llm.py:352-365`).
8. CRM deduplication lacks normalized/database-enforced uniqueness and company policy (`app/services/crm.py:40-53`).
9. Important database indexes and check constraints are missing (initial migration contains no workload indexes).
10. Tool-call history promised by architecture is not persisted (`docs/ARCHITECTURE.md:106-110`; no `tool_calls` model/table).
11. Errors expose raw internal exception strings in API state (`app/tools/base.py:85-93`, `app/agent/agent.py:250-261`).
12. Docker image runs as root, includes build/test dependencies and Qdrant uses `latest` (`Dockerfile:1-23`, `docker-compose.yml:30-31`).
13. Frontend lacks request locking, history restore, robust error states, mobile breakpoint and accessible controls.
14. The implementation plan remains stale: phases are marked pending despite completed code (`IMPLEMENTATION_PLAN.json`).

## Positive Controls

- SQLAlchemy is used instead of arbitrary SQL.
- Tool names are constrained by enums/lists.
- Tool inputs receive basic Pydantic validation.
- Lead scoring is deterministic and configuration-driven.
- `.env` and database files are Git-ignored.
- No live API key was found in tracked files/history reviewed by the auditors.
- Chat output uses `textContent`; XSS is localized to the leads table implementation.
- Redis messages have a configured TTL when Redis is available.
- Existing tests run without production API keys.

## Release Decision

Do not deploy this revision to a public environment or process real client data.

Minimum release gate:

1. Close all P0 items in `docs/REMEDIATION_PLAN.json`.
2. Add authentication, authorization and tenant-isolation tests.
3. Prove transactionally safe booking under concurrent requests.
4. Pass direct and indirect prompt-injection evals.
5. Run PostgreSQL/Redis/Qdrant integration tests and Alembic drift checks in CI.
6. Align customer-facing claims with implemented controls.
7. Complete UAT and production runbooks.
