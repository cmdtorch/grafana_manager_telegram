from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_ADMIN_CHAT_ID: int
    TELEGRAM_CREATOR_IDS: list[int]

    GRAFANA_URL: str = "http://localhost:3000"
    GRAFANA_USER: str = "admin"
    GRAFANA_PASSWORD: str


settings = Settings()
