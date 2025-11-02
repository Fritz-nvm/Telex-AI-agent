from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    TELEX_API_BASE_URL: str = "https://api.telex.im"
    TELEX_A2A_SEND_PATH: str = "/a2a/message"
    TELEX_BOT_TOKEN: str

    SCHEDULER_TIMEZONE: str = "UTC"


settings = Settings()
