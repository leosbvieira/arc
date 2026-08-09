from pathlib import Path

from pydantic import field_validator
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

    # Calendários ICS. As URLs são segredos e ficam somente no ambiente, conforme a lei 7.
    gcal_ics_url: str = ""
    outlook_ics_url: str = ""
    ics_timeout: int = 15
    ics_cache_ttl: int = 900

    # Escrita SOMENTE no Google Calendar pessoal. Outlook permanece read-only.
    google_calendar_client_id: str = ""
    google_calendar_client_secret: str = ""
    google_calendar_refresh_token: str = ""
    google_calendar_id: str = "primary"
    google_calendar_timeout: int = 20

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
    #
    # A TARIFA é a tabela da proposta C2, a mesma que o app exibe em `theme.ts`.
    # Antes daqui o BFF pagava só `pontos_por_rotina: 1` e mais nada: o app
    # prometia "+80" no botão de fechar o dia e o servidor creditava zero. Os
    # limiares de nível abaixo (700/1700/3400/6800) são a prova de qual lado
    # estava errado — a 1 ponto por rotina, N4 levaria mais de três anos; na
    # tarifa da C2, um dia executado inteiro vale ~200 e N1 chega em 4 dias.
    # Cada tarifa tem um evento que a paga; o mapa mora em `pontos._EVENTOS_PAGOS`.
    pontos_por_rotina: int = 20       # cada rotina marcada como feita no fechamento
    pontos_por_tarefa: int = 10       # `task_completed`
    pontos_por_captura: int = 5       # `capture_done` (a captura MATERIALIZADA)
    pontos_por_fechamento: int = 80   # `closing_approved`
    pontos_por_shutdown: int = 30     # `shutdown`
    pontos_por_despejo: int = 40      # `despejo_escrito` (fechou COM texto bruto)
    # O desconto acompanha a rotina na mesma razão que o Leo travou: um padrão
    # custa 3 rotinas, e a semana inteira nunca passa de 10. Escalar o ganho sem
    # escalar isto mataria a punição em silêncio — 10 pontos numa semana de ~1700
    # é ruído, e a punição foi a peça que ele sustentou duas vezes contra a IA.
    desconto_padrao: int = 60         # 3 × rotina — por rotina EM PADRÃO, 1x/semana
    teto_desconto_semanal: int = 200  # 10 × rotina — o teto de desconto da semana
    ciclo_semanas: int = 12           # 12 Week Year
    ciclo_inicio: str = "2026-07-06"  # segunda-feira âncora do 1º ciclo
    # Limiares VITALÍCIOS de N1, N2, N3, N4 (abaixo do 1º = N0). Ver pontos.py:
    # o nível é função do PICO histórico do saldo, então jamais regride (lei 4).
    nivel_limiares: list[int] = [700, 1700, 3400, 6800]

    # server-to-server
    internal_token: str = DEFAULTS["internal_token"]

    db_path: str = str(_PROJECT_DIR / "data.db")

    @field_validator("db_path")
    @classmethod
    def ancorar_db_path(cls, valor: str) -> str:
        """Caminho relativo vira absoluto, ancorado no projeto.

        `sqlite3.connect` resolve contra o CWD, então `DB_PATH=data.db` faz o banco
        depender de onde o servidor foi iniciado. Subir de `projects/escritorio/`
        em vez de `projects/escritorio/bff/` cria um banco novo e VAZIO em silêncio
        — sem erro, sem aviso: pontos, rotinas, capturas e histórico somem da tela
        e voltam quando você inicia do lugar certo. Já aconteceu: existe um
        `projects/escritorio/data.db` de 05/07 com zero linhas."""
        caminho = Path(valor)
        return valor if caminho.is_absolute() else str(_PROJECT_DIR / caminho)

    # Lei 7 dentro da própria ferramenta: sem isto, QUALQUER traceback que mencione
    # `settings` (um assert do pytest, um erro 500 com locals, um log de debug)
    # despeja senha, JWT secret, PAT do vault e token do ClickUp em texto claro —
    # no terminal, no CI e em qualquer transcript. O repr é caminho de vazamento.
    _CAMPOS_SIGILOSOS = ("password", "secret", "token", "pat", "key", "chat_id", "url")

    def __repr_args__(self):
        for nome, valor in super().__repr_args__():
            sigiloso = any(marca in (nome or "").lower() for marca in self._CAMPOS_SIGILOSOS)
            yield nome, ("<oculto>" if sigiloso and valor else valor)


settings = Settings()
