from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    openai_api_key: str

    # app
    app_name: str = "FinSightAI"
    app_version: str = "0.1.0"
    debug: bool = False

    class Config:
        env_file = Path(__file__).resolve().parents[1] / ".env"
        env_file_encoding = "utf-8"


settings = Settings()
