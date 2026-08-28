from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 설정. Supabase는 인프라로만 사용 (경계 룰: docs/03-dev-plan.md)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/withcare"
    supabase_url: str = ""
    supabase_service_key: str = ""


settings = Settings()
