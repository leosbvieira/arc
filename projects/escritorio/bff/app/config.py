from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Config lida de variáveis de ambiente / .env. Segredos NUNCA no código."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # auth single-user
    app_password: str = "troque-esta-senha"
    jwt_secret: str = "dev-only-secret-troque-no-.env-com-string-longa"
    jwt_ttl_hours: int = 720

    # Hermes (em mock por padrão, pra rodar sem o VPS)
    hermes_mock: bool = True
    hermes_base_url: str = "http://localhost:8080"
    hermes_api_key: str = ""
    hermes_profile_capture: str = "Leitura"

    # push
    expo_push_url: str = "https://exp.host/--/api/v2/push/send"

    # server-to-server (cron do Hermes -> /internal/notify)
    internal_token: str = "troque-token-interno"

    db_path: str = "data.db"


settings = Settings()
