from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Groq (hosted, free tier)
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.1-8b-instant"


settings = Settings()
