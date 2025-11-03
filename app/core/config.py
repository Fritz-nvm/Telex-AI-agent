from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve project root and .env so it loads even if you start uvicorn from a subfolder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    # Loads from OS environment first; .env is used for local dev
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Groq
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.1-8b-instant"


settings = Settings()
