from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_DIR / ".env"

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

    # Pontos + Conquistas N1-4 (P2 item 3) — números travados pelo Leo em 12/jul.
    # "fazer ganha, furar desconta POUCO": o ganho é diário e o desconto é raro
    # (só em padrão), uma vez por semana por rotina, e ainda passa por um teto.
    # `routine_miss_threshold` (acima) é o limiar do padrão — NÃO se duplica aqui.
    pontos_por_rotina: int = 1        # cada rotina marcada como feita no fechamento
    desconto_padrao: int = 3          # por rotina EM PADRÃO, 1x/semana (não por furo)
    teto_desconto_semanal: int = 10   # o desconto de uma semana nunca passa disso
    ciclo_semanas: int = 12           # 12 Week Year
    ciclo_inicio: str = "2026-07-06"  # segunda-feira âncora do 1º ciclo
    # Limiares VITALÍCIOS de N1, N2, N3, N4 (abaixo do 1º = N0). Ver pontos.py:
    # o nível é função do PICO histórico do saldo, então jamais regride (lei 4).
    nivel_limiares: list[int] = [700, 1700, 3400, 6800]

    # server-to-server
    internal_token: str = DEFAULTS["internal_token"]

    db_path: str = str(_PROJECT_DIR / "data.db")


settings = Settings()
