"""
Centralized application configuration.
All values are loaded from environment variables (.env locally, Railway
variables in production). Never hardcode secrets here.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    APP_NAME: str = "voice-patient-registration"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # --- Database (PostgreSQL) ---
    DATABASE_URL: str  # postgresql+asyncpg://user:pass@host:port/db

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 60

    # --- OpenAI (used by Vapi as the LLM provider) ---
    OPENAI_API_KEY: str = ""

    # --- Vapi ---
    VAPI_API_KEY: str = ""          # private key, server-side only
    VAPI_PUBLIC_KEY: str = ""
    VAPI_ASSISTANT_ID: str = ""
    VAPI_WEBHOOK_SECRET: str = ""   # shared secret to verify inbound webhooks
    VAPI_SERVER_URL: str = ""       # https://<your-app>.up.railway.app/vapi/webhook

    # --- Twilio (OPTIONAL — only needed for a non-US number or porting an
    # existing number you already own. Vapi provides a free US number
    # natively, which is what setup_vapi.py uses by default.) ---
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    USE_TWILIO_IMPORT: bool = False  # set True only if importing a Twilio number

    # --- Langfuse (observability) ---
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
