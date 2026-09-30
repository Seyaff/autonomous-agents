import os

# --- TEMP DEBUG: runs before anything else ---
print("=== ENV DEBUG ===")
print("REDIS_URI in os.environ:", "REDIS_URI" in os.environ)
print("REDIS_URL in os.environ:", "REDIS_URL" in os.environ)
print("REDIS_URI value prefix:", os.environ.get("REDIS_URI", "<not set>")[:30])
print("REDIS_URL value prefix:", os.environ.get("REDIS_URL", "<not set>")[:30])
print("Total env vars:", len(os.environ))
print("=================")
# --- END TEMP DEBUG ---

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Project"
    MONGO_URI: str
    DATABASE_NAME: str

    GROQ_API_KEY: str
    PINECONE_API_KEY: str

    WHATSAPP_VERIFY_TOKEN: str = Field(
        validation_alias=AliasChoices(
            "META_VERIFY_TOKEN", "WHATSAPP_VERIFY_TOKEN"
        )
    )
    WHATSAPP_TOKEN: str = Field(
        validation_alias=AliasChoices("WHATSAPP_TOKEN")
    )
    WHATSAPP_PHONE_NUMBER_ID: str = Field(
        validation_alias=AliasChoices("WHATSAPP_PHONE_NUMBER_ID")
    )
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = Field(
        validation_alias=AliasChoices("WHATSAPP_BUSINESS_ACCOUNT_ID")
    )

    HF_TOKEN: str

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_CALLBACK_URL: str = "http://localhost:8000/api/v1/auth/google/callback"
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    FRONTEND_URL: str = "http://localhost:3000"
    JWT_SECRET_KEY: str = "default_secret_key_change_in_production"
    SESSION_SECRET_KEY: str = "default_session_secret_key"
    JWT_ALGORITHM: str = "HS256"

    TAVILY_API_KEY: str = ""
    APIFY_API_TOKEN: str = ""
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""

    # Accepts either REDIS_URI or REDIS_URL from env
    REDIS_URI: str = Field(
        validation_alias=AliasChoices("REDIS_URI", "REDIS_URL"),
        description="The redis uri for memory",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()