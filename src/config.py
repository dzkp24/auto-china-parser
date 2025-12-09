from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    PROXY_URL: str | None = None  
    
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore" 

settings = Settings()