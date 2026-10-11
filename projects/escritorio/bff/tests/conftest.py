"""Higiene do ambiente de teste.

W4 adicionou `_guard_default_secrets()` no `lifespan`: o boot é bloqueado se qualquer
segredo em `config.DEFAULTS` permanecer no valor default. Os testes que sobem o app via
`with TestClient(...)` executam o lifespan de verdade — e o `.env` real do Leo ainda mantém
`internal_token` no default, o que derrubaria esses testes.

Setamos os segredos guardados para valores não-default AQUI, no nível de módulo do conftest:
o pytest importa o conftest antes dos módulos de teste, então isto vale inclusive para
`test_digest_v2.HDR`, que captura `settings.internal_token` no import. Só a sessão de teste é
afetada; o `.env` não é tocado.
"""
import tempfile
from pathlib import Path

import httpx
import pytest

from app import hermes_client, ritos, store
from app.config import DEFAULTS, settings

# Os valores têm de passar pelo guard novo (sem marcador de placeholder e com o
# tamanho mínimo de `config.MIN_SECRET_LEN`), por isso o sufixo comprido.
for _field in DEFAULTS:
    setattr(settings, _field, f"test-{_field}-" + "0123456789abcdef" * 2)

# `_guard_tasks_source()` recusa `TASKS_SOURCE=clickup` sem token — e o `.env`
# do Leo tem clickup. A suíte roda SEMPRE em mock; testes que precisam do source
# clickup setam os dois campos via monkeypatch.
settings.tasks_source = "mock"
# Idem pro Hermes: o `.env` deste PC roda com HERMES_MOCK=false (Codex real) e
# `test_port_limites_e_reserva` devolvia 502 por tentar o binário de verdade.
settings.hermes_mock = True

# --- as credenciais REAIS não sobrevivem ao import do conftest ----------------
# O loop acima só varre `DEFAULTS`, que tem TRÊS chaves (app_password, jwt_secret,
# internal_token). Todo o resto do `.env` do Leo continuava vivo durante a suíte
# inteira: `github_pat` (o PAT emprestado, com escrita no vault), `clickup_token`
# e `telegram_bot_token`. A única coisa que impedia uma escrita de verdade eram os
# ~25 monkeypatches de `write_raw` espalhados por 10 arquivos de teste — ou seja,
# um stub esquecido num teste novo bastava pra suíte fazer um PUT no vault real.
#
# O valor seguro aqui é VAZIO, não um `test-xxx`: string vazia é o estado que o
# próprio código já entende como "não configurado", e cada módulo já tem o seu
# fail-fast nomeado pra isso —
#   * `vault_client._client()` levanta `VaultError("vault_nao_configurado")`;
#   * `tasks._use_clickup()` exige `bool(clickup_token)`, então a suíte cai
#     sozinha no source de mock, mesmo com `TASKS_SOURCE=clickup` no `.env`;
#   * `ics_client` reporta `nao_configurado` com URL vazia.
# Preencher com lixo (`test-github_pat`) faria o contrário: o código se acharia
# configurado e TENTARIA a chamada.
_CREDENCIAIS = (
    "github_pat",
    "clickup_token",
    "telegram_bot_token",
    "telegram_chat_id",
    "hermes_api_key",
    "gcal_ics_url",
    "outlook_ics_url",
    "google_calendar_client_id",
    "google_calendar_client_secret",
    "google_calendar_refresh_token",
)
for _field in _CREDENCIAIS:
    setattr(settings, _field, "")

# Defesa em profundidade: mesmo que alguém injete um PAT no teste, o repo apontado
# não é o do Leo.
settings.vault_repo = "testes/vault-que-nao-existe"

# --- db da suíte: temporário, por sessão ------------------------------------
# A maioria dos testes já aponta `db_path` pra um tmp_path próprio, mas nem todos
# (test_fixes_auditoria escreve pela store diretamente). Sem esta linha, esses testes
# batiam no `data.db` de PRODUÇÃO — e isso é ruim de duas formas:
#
# 1. A suíte enfileirava capturas de teste na fila real. O BFF de produção está de pé:
#    o worker dele drena `capture_queue` a cada 5s e ingeriria "conteúdo de teste" no
#    vault do Leo.
# 2. Corrida entre o worker de prod e a suíte: `process_pending()` pega a linha pendente
#    de MENOR id, então uma linha que sobrou da rodada anterior (ou que o worker ainda
#    não drenou) era processada no lugar da linha do teste — vermelho intermitente,
#    dependendo de quem chegasse primeiro.
#
# Um db temporário por SESSÃO preserva o compartilhamento entre testes do mesmo arquivo
# (que test_fixes_auditoria assume) e nasce limpo a cada rodada.
_TMP_DB = Path(tempfile.mkdtemp(prefix="escritorio-tests-")) / "test.db"
settings.db_path = str(_TMP_DB)
store.init_db()


# --- nenhum teste fala com o Hermes de verdade -------------------------------
# Descoberto quando o recap da fatia 3 entrou no /compile: os testes de compile
# fakeiam `compile_reading`, mas o recap é OUTRA chamada, e ela caiu no `_oneshot`
# real — que dispara o `hermes.exe` como subprocesso. A suíte foi de 56s para 200s
# sem ninguém notar, porque a chamada é best-effort e o erro é engolido.
#
# Falhar alto e na hora é melhor que esperar: quem precisa do modelo stuba
# `_oneshot` no próprio teste, e essa substituição vence esta (o corpo do teste
# roda depois das fixtures).
@pytest.fixture(autouse=True)
def _sem_hermes_de_verdade(request, monkeypatch):
    # Quem testa o PRÓPRIO `_oneshot` (classificação de erro, serialização,
    # prompt por stdin) pede exceção com @pytest.mark.hermes_oneshot.
    if request.node.get_closest_marker("hermes_oneshot"):
        return

    async def proibido(*_args, **_kwargs):
        raise RuntimeError("hermes_oneshot_nao_stubado_neste_teste")

    monkeypatch.setattr(hermes_client, "_oneshot", proibido)


# --- nenhum teste abre socket ------------------------------------------------
# O cinto acima (credenciais vazias) tira o poder de escrever; este é o suspensório,
# e é o que fecha a classe inteira: sem PAT o vault falha nomeado, mas ClickUp,
# Telegram, Expo push e ICS ainda montariam um `httpx.AsyncClient` e SAIRIAM pra
# rede se um teste novo esquecesse o stub. Um teste que fala com a internet é lento,
# intermitente, e — no caso de um POST — muda dado de produção.
#
# O bloqueio mora na CLASSE de transporte real, não em `Client.send`, e isso é a
# escolha que faz ele não atrapalhar ninguém: quem fakeia HTTP nesta suíte usa
# `httpx.MockTransport` (test_vault_client, test_vault_retry, test_telegram,
# test_google_calendar), que é outra classe e passa intocada. O `TestClient` do
# Starlette também tem transporte próprio (ASGI, em processo), então subir o app
# continua funcionando. Sobra exatamente o que a gente quer proibir: socket.
#
# Mesma filosofia do `_oneshot` acima — falhar alto e na hora, com o método e a URL
# no texto, em vez de esperar alguém notar a suíte lenta ou o dado estranho.
@pytest.fixture
def nudge_no_horario(monkeypatch):
    """Para testes de nudge que NÃO são sobre horário (copy, dedupe, agregados).

    `/internal/nudge` recusa rito fora da janela, e a janela é medida contra o relógio
    de verdade — então um teste de copy passava de manhã e falhava à noite. Aqui a
    guarda sai do caminho, explicitamente, em vez de fingir um relógio.

    De propósito NÃO é autouse: um teste novo que poste um nudge vai falhar com
    `skipped: atrasado` e descobrir a guarda, que é como se aprende que ela existe.
    Quem testa a guarda em si usa `ritos.atrasado` direto (test_nudge_atrasado.py).
    """
    monkeypatch.setattr(ritos, "atrasado", lambda *_args, **_kwargs: False)


@pytest.fixture(autouse=True)
def _sem_rede_de_verdade(request, monkeypatch):
    # Escape hatch simétrico ao `hermes_oneshot`. Hoje ninguém usa: se você está
    # prestes a marcar um teste com isto, ele provavelmente não é um teste.
    if request.node.get_closest_marker("rede_de_verdade"):
        return

    def _bloqueia(_self, req, *_args, **_kwargs):
        raise RuntimeError(f"rede_real_bloqueada_no_teste: {req.method} {req.url}")

    async def _bloqueia_async(_self, req, *_args, **_kwargs):
        raise RuntimeError(f"rede_real_bloqueada_no_teste: {req.method} {req.url}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _bloqueia)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _bloqueia_async)
