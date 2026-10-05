import os

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Project"
    MONGO_URI: str
    DATABASE_NAME: str

    PINECONE_API_KEY: str

    # Owners who can add a second restaurant before it's generally available (comma-separated emails).
    BETA_OWNER_EMAILS: str = ""

    # Email (Resend). Off until RESEND_API_KEY is set.
    RESEND_API_KEY: str = ""
    # Resend's sandbox sender works without a verified domain, but only delivers to the Resend account owner.
    EMAIL_FROM: str = "Siyaf <onboarding@resend.dev>"
    FOUNDER_EMAIL: str = ""

    # Online payments for orders. Filled in from each provider's merchant account.
    JAZZCASH_MERCHANT_ID: str = ""
    JAZZCASH_PASSWORD: str = ""
    JAZZCASH_INTEGRITY_SALT: str = ""
    # Payment type sent to JazzCash. Empty lets the hosted page show all payment methods.
    JAZZCASH_TXN_TYPE: str = Field(default="", validation_alias=AliasChoices("JC_TXN_TYPE", "JAZZCASH_TXN_TYPE"))
    EASYPAISA_STORE_ID: str = ""
    EASYPAISA_HASH_KEY: str = ""
    PAYMENT_RETURN_URL: str = ""
    # Where the backend is reachable from the internet (through the Vercel proxy).
    PUBLIC_API_BASE: str = "https://siyaf.vercel.app/api"
    JAZZCASH_CHECKOUT_URL: str = "https://sandbox.jazzcash.com.pk/CustomerPortal/transactionmanagement/merchantform/"

    # Payments. 'dummy' charges nothing; a real gateway replaces it later.
    PAYMENTS_PROVIDER: str = Field(
        default="dummy",
        description="Which payment provider takes subscription payments.",
    )

    # --- LLM provider routing (dev: groq, prod: openai) ---
    LLM_PROVIDER: str = Field(
        default="groq",
        description="Which LLM provider agents use: 'groq' or 'openai'.",
    )
    # When the main provider hits its rate limit (e.g. Groq's daily cap), the turn is retried on this one.
    # Empty turns the fallback off.
    LLM_FALLBACK_PROVIDER: str = Field(default="openai", description="Provider to retry on when the main one is rate-limited. Empty to turn off.")
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1"

    # Fernet key for encrypting customers' WhatsApp tokens at rest. Required in production.
    TOKEN_ENCRYPTION_KEY: str = ""

    # Cheap model for memory extraction (runs after every customer message).
    # Kept separate from the reply model so memory costs stay low.
    MEMORY_GROQ_MODEL: str = "openai/gpt-oss-20b"
    MEMORY_OPENAI_MODEL: str = "gpt-4.1-mini"

    # Model for reading dishes out of a menu. Its own model, so menu reading doesn't
    # use up the reply model's per-minute token limit.
    MENU_GROQ_MODEL: str = "openai/gpt-oss-20b"
    MENU_OPENAI_MODEL: str = "gpt-4.1-mini"

    # Speech-to-text for customers' voice notes (Urdu).
    TRANSCRIBE_GROQ_MODEL: str = "whisper-large-v3-turbo"
    TRANSCRIBE_OPENAI_MODEL: str = "whisper-1"

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
    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("FRONTEND_URL", "FRONTEND_ORIGIN"),
    )

    @property
    def frontend_origin(self) -> str:
        """Where the app lives. If FRONTEND_URL isn't set for production, use the site the Google
        callback points at, so users aren't sent to localhost after signing in."""
        from urllib.parse import urlsplit

        configured = (self.FRONTEND_URL or "").rstrip("/")
        if configured and "localhost" not in configured:
            return configured
        callback = urlsplit(self.GOOGLE_CALLBACK_URL or "")
        if callback.scheme == "https" and callback.netloc and "localhost" not in callback.netloc:
            return f"{callback.scheme}://{callback.netloc}"
        return configured or "http://localhost:3000"
    JWT_SECRET_KEY: str = "default_secret_key_change_in_production"
    SESSION_SECRET_KEY: str = "default_session_secret_key"
    JWT_ALGORITHM: str = "HS256"

    # One-time secret used to bootstrap the single FOUNDER account.
    # Unset/blank disables the bootstrap endpoint entirely.
    FOUNDER_BOOTSTRAP_SECRET: str = ""

    TAVILY_API_KEY: str = ""
    APIFY_API_TOKEN: str = ""
    META_APP_ID: str = Field(default="", validation_alias=AliasChoices("APP_ID", "META_APP_ID"))
    META_APP_SECRET: str = Field(default="", validation_alias=AliasChoices("APP_SECRET", "META_APP_SECRET"))

    # Accepts either REDIS_URI or REDIS_URL from env
    REDIS_URI: str = Field(
        validation_alias=AliasChoices("REDIS_URI", "REDIS_URL"),
        description="The redis uri for memory",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()