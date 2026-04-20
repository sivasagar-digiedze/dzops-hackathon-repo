import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # App config
    PROJECT_NAME: str = "Aura Agent API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # DB config
    POSTGRES_SERVER: str = "aura_postgres"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "aura_agent"
    POSTGRES_PORT: str = "5432"
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Security config
    SECRET_KEY: str = "YOUR_SUPER_SECRET_KEY_HERE_CHANGE_IN_PROD"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"

    # Redis / Celery config
    REDIS_URL: str = "redis://localhost:6379/0"

    # Langfuse/LLM config
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    
    # vLLM (Mistral reasoning endpoint)
    #LLM_API_BASE: str = "http://localhost:8000/v1"

    LLM_API_BASE: str = "http://litellm:4000"
    #LLM_MODEL_NAME: str = "mistralai/Ministral-3-3B-Reasoning-2512"
    
    LLM_MODEL_NAME: str = "mistral-local"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)

settings = Settings()
