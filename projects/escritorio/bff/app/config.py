from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

DEFAULTS: dict[str, str] = {
    "app_password": "troque-esta-senha",
    "jwt_secret": "dev-only-secret-troque-no-.env-com-string-longa",
    "internal_token": "troque-token-interno",
}


class Settings(BaseSettings):
    """Config lida de variáveis de ambiente / .env. Segredos NUNCA no código."""

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # auth single-user
    app_password: str = DEFAULTS["app_password"]
    jwt_secret: str = DEFAULTS["jwt_secret"]
    jwt_ttl_hours: int = 720

    # Hermes (em mock por padrão, pra rodar sem o VPS)
    hermes_mock: bool = True
    hermes_base_url: str = "http://localhost:8080"
    hermes_api_key: str = ""
    hermes_profile_capture: str = "Capturas"
    hermes_bin: str = "hermes"
    hermes_timeout: int = 150
    capture_worker_interval: float = 5.0

    # ClickUp
    tasks_source: str = "mock"
    clickup_token: str = ""
    clickup_verify_ssl: str = "true"

    # Vault
    github_pat: str = ""
    vault_repo: str = "leosbvieira/aeternum"
    vault_branch: str = "main"

    # push
    expo_push_url: str = "https://exp.host/--/api/v2/push/send"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Digest v2
    staging_age_days: int = 3
    routine_miss_threshold: int = 3
    sensitive_areas: str = "Corpo,Saúde Mental"

    # server-to-server
    internal_token: str = DEFAULTS["internal_token"]

    db_path: str = "data.db"


settings = Settings()
