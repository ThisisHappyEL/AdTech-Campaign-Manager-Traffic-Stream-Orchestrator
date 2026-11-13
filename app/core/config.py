import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Keitaro Stream Manager"
    
    # Keitaro Settings
    KEITARO_BASE_URL: str = os.getenv("KEITARO_BASE_URL", "https://tlgk.host/admin_api/v1")
    KEITARO_API_KEY: str = os.getenv("KEITARO_API_KEY", "5149af94ff5da95812b918f31569d498")
    
    # Default Campaign Settings (из реальных данных Keitaro)
    DEFAULT_GROUP_ID: int = 9799         # VZ adrobot test
    DEFAULT_TRAFFIC_SOURCE_ID: int = 0
    DEFAULT_DOMAIN_ID: int | None = None
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./keitaro_manager.db")
    SYNC_DATABASE_URL: str = os.getenv("SYNC_DATABASE_URL", "sqlite:///./keitaro_manager.db")

    class Config:
        env_file = ".env"

settings = Settings()