import os
from dataclasses import dataclass
from pathlib import Path

# Optional: load .env for local dev (Railway uses env vars directly)
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
if ENV_PATH.exists():
    try:
        from dotenv import load_dotenv  # pip install python-dotenv (optional)

        load_dotenv(ENV_PATH)
    except Exception:
        pass

# Module-level access (if you prefer direct imports)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")


# Backward-compatible settings object
@dataclass(frozen=True)
class Settings:
    GROQ_API_KEY: str | None = GROQ_API_KEY
    GROQ_MODEL: str = GROQ_MODEL


settings = Settings()
