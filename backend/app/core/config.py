# Configuration
from pydantic_settings import BaseSettings, SettingsConfigDict

# I want a class that automatically reads from enviornment variables
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )  # Look for variables inside .env file and ignore any extra variables that are not defined in this class

    # Secrets
    openai_api_key: str
    market_data_api_key: str
    jwt_secret: str

    # Infrastructure
    database_url: str
    redis_url: str

    # Product
    default_model: str = "gpt-4.1"
    cheap_model: str = "gpt-4o-mini"
    max_run_turns: int = 25
    free_tier_reports_per_month: int = 5


settings = Settings()
