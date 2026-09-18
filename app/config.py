import os
from typing import Optional
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Autonomous Restaurant Operations Platform"
    APP_ENV: str = Field(default="development", validation_alias=AliasChoices("APP_ENV", "NODE_ENV"))
    DEBUG: bool = True
    PORT: int = 8000
    SECRET_KEY: str = "super_secret_dev_key_change_in_prod"

    # Meta WhatsApp Cloud API credentials
    META_APP_ID: Optional[str] = Field(default=None, validation_alias=AliasChoices("META_APP_ID", "APP_ID"))
    META_APP_SECRET: Optional[str] = Field(default=None, validation_alias=AliasChoices("META_APP_SECRET", "APP_SECRET"))
    META_ACCESS_TOKEN: Optional[str] = Field(default=None, validation_alias=AliasChoices("META_ACCESS_TOKEN", "WHATSAPP_TOKEN"))
    META_PHONE_NUMBER_ID: Optional[str] = Field(default=None, validation_alias=AliasChoices("META_PHONE_NUMBER_ID", "WHATSAPP_PHONE_NUMBER_ID"))
    META_WABA_ID: Optional[str] = Field(default=None, validation_alias=AliasChoices("META_WABA_ID", "WHATSAPP_BUSINESS_ACCOUNT_ID"))
    META_WEBHOOK_VERIFY_TOKEN: str = Field(default="siyafbro", validation_alias=AliasChoices("META_WEBHOOK_VERIFY_TOKEN", "WHATSAPP_VERIFY_TOKEN"))
    META_API_VERSION: str = "v21.0"
    META_GRAPH_URL: str = "https://graph.facebook.com"

    # Operational & Founder details
    OWNER_WHATSAPP_PHONE: Optional[str] = Field(default=None, validation_alias=AliasChoices("OWNER_WHATSAPP_PHONE", "OWNER_PHONE_NUMBER"))
    FOUNDER_PHONE_NUMBER: Optional[str] = None
    DEFAULT_RESTAURANT_ID: str = Field(default="da-pakhtun-dera", validation_alias=AliasChoices("DEFAULT_RESTAURANT_ID", "RESTAURANT_ID"))

    # Database: if DATABASE_URL not set in .env, default to sqlite
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./autonomous_agents.db",
        validation_alias=AliasChoices("DATABASE_URL")
    )

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI Model & Search Providers
    GOOGLE_API_KEY: Optional[str] = Field(default=None, validation_alias=AliasChoices("GOOGLE_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"))
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None
    APIFY_API_KEY: Optional[str] = None
    PINECONE_API_KEY: Optional[str] = None

    # File uploads
    STORAGE_DIR: str = "./uploads"

settings = Settings()
