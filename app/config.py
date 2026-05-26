import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "DocWatch V2"
    ENVIRONMENT: str = Field(default="production")
    
    # AI Settings
    AI_BASE_URL: str = Field(default="https://api.openai.com/v1")
    AI_API_KEY: str = Field(default="")
    AI_MODEL: str = Field(default="gpt-4o")
    
    # Database
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:////data/docwatch.db")
    
    # Webhooks
    WEBHOOK_URL: str = Field(default="")
    
    # Docker Event Debounce
    DEBOUNCE_SECONDS: int = Field(default=60, description="Group crashes for the same container within this window")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("docwatch")
