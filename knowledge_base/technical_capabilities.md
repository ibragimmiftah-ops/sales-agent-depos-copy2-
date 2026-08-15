# Technical Capabilities & Limitations

## Technology Stack

- **Backend**: Python, FastAPI, Pydantic, SQLAlchemy, Alembic.
- **LLMs**: OpenAI GPT-4o / GPT-4o-mini, Anthropic Claude (swap via config).
- **Vector DB**: Qdrant (production), ChromaDB (local development).
- **Embeddings**: OpenAI text-embedding-3-small, with keyword fallback for tests.
- **Memory**: Redis for short-term conversation history, PostgreSQL for long-term lead data.
- **Observability**: structured JSON logs, conversation tracing, tool-call logging.
- **Deployment**: Docker, Docker Compose, cloud-ready.

## Supported Integrations

- CRM: HubSpot, Bitrix24, Zoho, Pipedrive, Salesforce, custom REST APIs.
- Calendars: Google Calendar, Calendly-style slots, custom calendar APIs.
- Messengers: Telegram, WhatsApp (via official API partners), website widgets.
- Communication: email, SMS via providers, Slack.

## Capabilities

- Intent detection and structured output.
- Multi-turn qualification with state machine.
- RAG retrieval with metadata filtering.
- Lead scoring and quality classification.
- Tool calling (CRM, calendar, knowledge base, scoring).
- Human handoff and fallback flows.
- Conversation analytics and audit events.

## Limitations

- AI agents are not magic. They work best when processes and knowledge base are documented.
- Complex negotiations or highly sensitive cases should be escalated to humans.
- LLM API costs are separate from our service fee and depend on usage volume.
- Multi-channel WhatsApp requires official Business API access (Meta approval may take time).
- Real-time voice calls are not included in the standard AI Sales Agent package.

## Data & Compliance

- API keys and secrets are stored in environment variables, never in code.
- Data can be hosted in EU or US cloud regions.
- GDPR-aligned data handling available.
- Audit logs are retained for 12 months by default.
