"""Application configuration via environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "NovaFlow AI Sales Agent"
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
    QDRANT_COLLECTION_NAME: str = "novaflow_kb"
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


settings = Settings()
