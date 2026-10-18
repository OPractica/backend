from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./dev.db"
    secret_key: str = "change-me-in-production"
    access_minutes: int = 15
    refresh_days: int = 30
    code_ttl_minutes: int = 10
    office_tz: str = "Europe/Chisinau"
    open_hour: int = 9
    close_hour: int = 19
    default_start: str = "09:00"
    default_end: str = "18:00"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Workplace Booking <no-reply@localhost>"
    smtp_tls: bool = True


settings = Settings()
