from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 설정. Supabase는 인프라로만 사용 (경계 룰: docs/03-dev-plan.md)."""

    model_config = SettingsConfigDict(env_file=Path(__file__).parents[1] / ".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/withcare"
    supabase_url: str = ""
    supabase_service_key: str = ""
    # P7: 독촉·리마인드 스케줄러 (테스트·마이그레이션에선 꺼짐이 기본)
    scheduler_enabled: bool = False
    # P11: CORS 허용 오리진 (쉼표 구분). prod 배포 시 실제 도메인으로 교체
    cors_origins: str = "http://localhost:8081"


settings = Settings()
