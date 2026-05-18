from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    tessa_env: str = "development"
    tessa_domain: str = "tessa.ki-c.pro"
    public_base_url: str = "https://tessa.ki-c.pro"
    tessa_workspaces_dir: str = "/workspaces"
    default_workspace: str = "company-default"

    # Security
    secret_key: str = "dev-insecure-secret"
    fernet_key: str = ""
    session_ttl_minutes: int = 720
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    # Postgres
    postgres_db: str = "tessa"
    postgres_user: str = "tessa"
    postgres_password: str = "tessa"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # Infra
    redis_url: str = "redis://redis:6379/0"
    qdrant_url: str = "http://qdrant:6333"
    litellm_base_url: str = "http://litellm:4000"
    litellm_master_key: str = "sk-tessa-master"

    # Provider keys (optional; admin UI can override)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""

    # Embeddings
    embedding_provider: str = "mock"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # Bootstrap admin
    bootstrap_admin_username: str = "kai"
    bootstrap_admin_display_name: str = "Kai"
    bootstrap_admin_password: str = "change_me_initial_password"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_production(self) -> bool:
        return self.tessa_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
