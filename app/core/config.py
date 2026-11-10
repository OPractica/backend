from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    cors_origin_regex: str = ""

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@office-booking.local"

    graph_tenant_id: str = ""
    graph_client_id: str = ""
    graph_client_secret: str = ""
    graph_sender: str = ""

    booking_max_hours: int = 10
    office_open_hour: int = 9
    office_close_hour: int = 19
    booking_min_minutes: int = 15

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()
