from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    debug: bool = False
    database_url: str = 'sqlite:///./todos.db'
    secret_key: str = 'change-me-in-production'
    jwt_algorithm: str = 'HS256'
    jwt_expire_minutes: int = 30

    class Config:
        env_file = '.env'


@lru_cache
def get_settings() -> Settings:
    return Settings()
