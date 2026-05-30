from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Anime Recommender Enterprise"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # LLM
    GROQ_API_KEY: str
    MODEL_NAME: str = "llama-3.1-8b-instant"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "chroma_db"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 10

    # Groq pricing per million tokens (as of 2025)
    COST_INPUT_PER_M_TOKENS: float = 0.05
    COST_OUTPUT_PER_M_TOKENS: float = 0.08

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
