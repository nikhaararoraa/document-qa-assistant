from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase (Auth + API)
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # Postgres (Alembic + direct DB access; must be the direct/session connection)
    database_url: str

    # OpenAI (LLM, once the chat layer is wired up)
    openai_api_key: str

    # Embeddings — local Ollama, not OpenAI (see backend/ingest/embeddings.py)
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    ollama_base_url: str = "http://localhost:11434"

    # Server
    allowed_origins: str = "http://localhost:5173"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def sqlalchemy_database_url(self) -> str:
        """`database_url` with an explicit driver so SQLAlchemy picks psycopg (v3),
        the driver we actually install, instead of defaulting to psycopg2."""
        url = self.database_url
        if url.startswith("postgresql+"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        return url


settings = Settings()
