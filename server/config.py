"""Environment-backed configuration for the FlowPilot backend."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load the documented environment variables and their defaults."""

    model_config = SettingsConfigDict(case_sensitive=False, env_file=".env", extra="ignore")

    flowpilot_env: str = "development"
    flowpilot_port: int = 8000
    flowpilot_db_path: str = "./data/flowpilot.db"
    flowpilot_cors_origins: str = "http://localhost:5173"
    gemini_api_key: str | None = None
    flowpilot_default_provider: str = "deterministic"
    flowpilot_gemini_model: str | None = None
    flowpilot_llm_timeout_s: int = 15
    flowpilot_demo_timestamp: str | None = "2026-10-22T09:00:00+05:30"
    flowpilot_log_level: str = "INFO"


settings = Settings()
