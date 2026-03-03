from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env')
    openai_api_key: str
    chroma_persist_path: str = './chroma_data'
    model_name: str = 'gpt-4o-mini'


settings = Settings()

