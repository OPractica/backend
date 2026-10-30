from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str
    groq_api_key: str
    google_api_key: str = ""
    llm_model: str = "gemini-3.5-flash-lite"
    office_timezone: str = "Europe/Chisinau"
    jwt_secret: str

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@office-booking.local"


settings = Settings()
