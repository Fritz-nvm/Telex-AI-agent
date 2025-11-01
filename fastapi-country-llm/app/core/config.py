from pydantic import BaseSettings

class Settings(BaseSettings):
    api_key: str
    llm_endpoint: str
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()