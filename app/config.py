from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    freshservice_domain: str
    freshservice_api_key: str
    middleware_api_key: str
    app_env: str = 'development'
    log_level: str ='INFO'
    
    @property
    def freshservice_base_url(self) -> str:
        return f'https://{self.freshservice_domain}api/v2/'
      
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        
@lru_cache()
def get_settings() -> Settings:
    return Settings()