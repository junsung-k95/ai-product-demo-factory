from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # AI API keys (optional — Claude Code agent uses its own auth)
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    environment: str = "development"
    log_level: str = "INFO"

    # Demo generation config
    demos_output_dir: str = "/tmp/demo-factory/demos"
    max_turns_per_demo: int = 25
    max_budget_usd: float = 15.0


settings = Settings()
