from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Project"
    MONGO_URI: str
    DATABASE_NAME: str

    GROQ_API_KEY: str
    PINECONE_API_KEY: str

    # Checks META_VERIFY_TOKEN first, falls back to WHATSAPP_VERIFY_TOKEN
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
    
    HF_TOKEN:str


    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()