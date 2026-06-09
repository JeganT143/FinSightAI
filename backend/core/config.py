import os
from pydantic_settings import BaseSettings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ENV_FILE = os.path.join(BASE_DIR, ".env")


class Settings(BaseSettings):
    openai_api_key: str
    database_url: str
    app_name: str = "FinSightAI"
    app_version: str = "0.1.0"
    debug: bool = False

    class Config:
        env_file = ENV_FILE
        env_file_encoding = "utf-8"


settings = Settings()
