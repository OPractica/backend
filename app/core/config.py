from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    DARABASE_URL: str
    groq_api_key: str
    groq_model: str = "qwen/qwen3.8-27b"
    office_timezone: str = "Europe/Chisinau"
    jwt_secret: str


settings = Settings()