"""Application configuration via environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "AI Sales Agent"
    ENVIRONMENT: str = "development"
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sales_agent"

    # Redis (short-term memory)
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_SHORT_TERM_TTL_SECONDS: int = 86400

    # Vector store (RAG)
    VECTOR_STORE_PROVIDER: str = "qdrant"  # qdrant | chroma
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_NAME: str = "sales_agent_kb"
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # Embeddings
    EMBEDDING_PROVIDER: str = "openai"  # openai | keyword
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # LLM
    LLM_PROVIDER: str = "openai"  # openai | anthropic | mock
    LLM_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 2048

    # Calendar
    DEFAULT_TIMEZONE: str = "Europe/Helsinki"
    BUSINESS_HOURS_START: int = 9
    BUSINESS_HOURS_END: int = 17
    SLOT_DURATION_MINUTES: int = 30

    # Conversation
    MAX_CONVERSATION_HISTORY: int = 20

    # Scoring
    SCORING_CONFIG_PATH: str = "config/scoring.yaml"

    # Paths
    KNOWLEDGE_BASE_DIR: str = "knowledge_base"
    FRONTEND_DIR: str = "frontend"

    # Security
    SECRET_KEY: str = Field(default="change-me-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # Limits / budgets
    MAX_MESSAGE_LENGTH: int = 2000
    MAX_CONVERSATION_TURNS: int = 50
    MAX_TOOL_CALLS_PER_RUN: int = 5
    MAX_RAG_TOP_K: int = 10
    RATE_LIMIT_CHAT_PER_MINUTE: int = 20
    RATE_LIMIT_PUBLIC_TOKEN_PER_MINUTE: int = 10
    RATE_LIMIT_OPERATOR_PER_MINUTE: int = 120
    REQUEST_TIMEOUT_SECONDS: float = 30.0
    LLM_TIMEOUT_SECONDS: float = 20.0
    TOOL_TIMEOUT_SECONDS: float = 10.0


settings = Settings()
