"""Application configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5433/hermes_bd"
    )
    default_sender_name: str = "Hermes BD Team"
    default_sender_company: str = "Hermes Agent"
    default_product_offering: str = (
        "AI-powered autonomous agents for sales, support, and operations"
    )
    follow_up_days: int = 3

    # Code agent backend: "nous_hermes" (Nous Research agent) or "openai" (direct GPT)
    code_agent_backend: str = "nous_hermes"


settings = Settings()
