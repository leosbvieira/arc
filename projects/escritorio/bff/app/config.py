from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env fica na raiz do bff/ (um nível acima do pacote app/). Caminho ABSOLUTO pra o
# .env ser lido independentemente de onde o uvicorn é iniciado (CWD não importa).
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Config lida de variáveis de ambiente / .env. Segredos NUNCA no código."""

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # auth single-user
    app_password: str = "troque-esta-senha"
    jwt_secret: str = "dev-only-secret-troque-no-.env-com-string-longa"
    jwt_ttl_hours: int = 720

    # Hermes (em mock por padrão, pra rodar sem o VPS)
    hermes_mock: bool = True
    hermes_base_url: str = "http://localhost:8080"
    hermes_api_key: str = ""
    hermes_profile_capture: str = "Capturas"
    # Integração real = chamar a CLI do Hermes em oneshot (`hermes -z`), não HTTP.
    hermes_bin: str = "hermes"        # caminho do hermes.exe (ou "hermes" se no PATH)
    hermes_timeout: int = 150         # segundos por chamada (o agente pode usar tools)

    # ClickUp (fonte real das tarefas — porta REST, não MCP)
    tasks_source: str = "mock"          # "mock" | "clickup"
    clickup_token: str = ""             # pk_...
    clickup_verify_ssl: str = "true"    # "true" | "false" | caminho do .pem da CA

    # Vault (escrita determinística via GitHub Contents API — o BFF segura a caneta)
    github_pat: str = ""                        # PAT fine-grained com Contents:write no repo do vault
    vault_repo: str = "leosbvieira/aeternum"    # owner/repo do vault
    vault_branch: str = "main"                  # branch alvo das escritas

    # push
    expo_push_url: str = "https://exp.host/--/api/v2/push/send"

    # server-to-server (cron do Hermes -> /internal/notify)
    internal_token: str = "troque-token-interno"

    db_path: str = "data.db"


settings = Settings()
