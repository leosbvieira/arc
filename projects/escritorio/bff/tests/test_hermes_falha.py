"""Distinguir "o Hermes caiu" de "a cota acabou".

O Hermes já sabe a diferença desde o PR #33168: `hermes_cli/auth.py` classifica o 429
do refresh como `codex_rate_limited` com `relogin_required=False`, e o `format_auth_error`
nunca sugere reautenticar nesse caso. Mas o BFF reduzia TODA falha ao mesmo
`RuntimeError("hermes_error")`, então essa distinção morria no stderr do subprocesso e o
celular mostrava "hermes indisponível" — igualzinho a PC desligado, timeout ou binário
sumido.

A lei 7 continua valendo e é o que limita o conserto: o que atravessa é o CÓDIGO da falha
e, quando existe, um inteiro de segundos. Prompt, stdout e stderr nunca.
"""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import hermes_client, main
from app.config import settings
from app.main import require_auth

# Estes testes SAO sobre o `_oneshot`; a trava do conftest o substituiria.
pytestmark = pytest.mark.hermes_oneshot


@pytest.fixture
def sem_mock(monkeypatch):
    monkeypatch.setattr(settings, "hermes_mock", False)


def _proc(returncode=1, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def _falha_com(monkeypatch, **kwargs):
    async def fake_to_thread(fn, *a, **kw):
        return _proc(**kwargs)

    monkeypatch.setattr(hermes_client.asyncio, "to_thread", fake_to_thread)


# --- classificação -----------------------------------------------------------


async def test_quota_esgotada_vira_codigo_proprio(sem_mock, monkeypatch):
    # Mensagem verbatim do Hermes (hermes_cli/auth.py:3630).
    _falha_com(
        monkeypatch,
        stderr=(
            "Codex provider quota exhausted (429); retry after 120s. "
            "Credentials are still valid."
        ),
    )

    with pytest.raises(hermes_client.HermesFalhou) as exc:
        await hermes_client._oneshot("qualquer prompt")

    assert exc.value.code == "hermes_quota"
    assert exc.value.retry_apos_s == 120


async def test_quota_sem_retry_after_ainda_e_quota(sem_mock, monkeypatch):
    # O `Retry-After` é best-effort no Hermes (`_parse_retry_after_seconds` devolve
    # None em formato de data). Não saber quando voltar não muda o que aconteceu.
    _falha_com(
        monkeypatch,
        stderr="Codex provider quota exhausted (429). Credentials are still valid;",
    )

    with pytest.raises(hermes_client.HermesFalhou) as exc:
        await hermes_client._oneshot("p")

    assert exc.value.code == "hermes_quota"
    assert exc.value.retry_apos_s is None


async def test_refresh_token_consumido_por_outro_cliente(sem_mock, monkeypatch):
    # O caso que o Leo consegue reproduzir sozinho: o `codex` CLI dele e o Hermes
    # dividem o mesmo refresh token, e quem refresca primeiro consome o do outro.
    _falha_com(
        monkeypatch,
        stderr=(
            "Codex refresh token was already consumed by another client "
            "(e.g. Codex CLI or VS Code extension)."
        ),
    )

    with pytest.raises(hermes_client.HermesFalhou) as exc:
        await hermes_client._oneshot("p")

    assert exc.value.code == "hermes_credencial"


async def test_falha_desconhecida_continua_hermes_error(sem_mock, monkeypatch):
    # Assinatura que o Hermes mudar cai aqui — degrada para o comportamento de antes
    # desta mudança, que é o certo. Nada quebra; só se perde a distinção.
    _falha_com(monkeypatch, stderr="Traceback (most recent call last): ...")

    with pytest.raises(hermes_client.HermesFalhou) as exc:
        await hermes_client._oneshot("p")

    assert exc.value.code == "hermes_error"
    assert exc.value.retry_apos_s is None


async def test_lei_7_nem_o_prompt_nem_a_saida_vazam(sem_mock, monkeypatch):
    segredo = "conteudo-ultrassecreto-do-usuario"
    _falha_com(
        monkeypatch,
        stdout=f"eco do {segredo}",
        stderr=f"quota exhausted; retry after 60s; contexto: {segredo}",
    )

    with pytest.raises(hermes_client.HermesFalhou) as exc:
        await hermes_client._oneshot(segredo)

    assert segredo not in str(exc.value)
    assert segredo not in repr(exc.value)
    assert str(exc.value) == "hermes_quota"


async def test_resposta_bem_sucedida_nunca_e_classificada(sem_mock, monkeypatch):
    # Se o Leo perguntar ao Mentor "o que é quota exhausted?", a resposta contém a
    # assinatura. Com returncode 0 o texto é RESPOSTA, não diagnóstico — só a saída de
    # um processo que já falhou é classificada.
    _falha_com(
        monkeypatch,
        returncode=0,
        stdout="Quota exhausted quer dizer que a cota acabou; retry after 30s.",
    )

    reply = await hermes_client._oneshot("o que é quota exhausted?")

    assert reply.startswith("Quota exhausted quer dizer")


async def test_hermes_falhou_e_runtime_error(sem_mock, monkeypatch):
    # Os 7 pontos de chamada (captura, triagem, leitura, anki, diário, review, chat) já
    # capturam RuntimeError. A subclasse existe para NÃO mexer em nenhum deles.
    _falha_com(monkeypatch, stderr="qualquer coisa")

    with pytest.raises(RuntimeError):
        await hermes_client._oneshot("p")


async def test_excecao_do_subprocesso_ainda_vira_hermes_error(sem_mock, monkeypatch):
    async def explode(fn, *a, **kw):
        raise asyncio.TimeoutError("estourou o timeout de 150s")

    monkeypatch.setattr(hermes_client.asyncio, "to_thread", explode)

    with pytest.raises(hermes_client.HermesFalhou) as exc:
        await hermes_client._oneshot("p")

    assert exc.value.code == "hermes_error"


# --- o que o app recebe ------------------------------------------------------


def _chat(monkeypatch, exc: Exception, texto="oi"):
    async def boom(prompt):
        raise exc

    monkeypatch.setattr(settings, "hermes_mock", False)
    monkeypatch.setattr(hermes_client, "_oneshot", boom)
    main.app.dependency_overrides[require_auth] = lambda: "test"
    try:
        with TestClient(main.app) as client:
            return client.post("/chat", json={"text": texto, "mode": "Mentor"})
    finally:
        main.app.dependency_overrides.clear()


def test_chat_quota_e_503_com_retry_after(monkeypatch):
    # 503 e não 502: o Hermes está de pé. O que faltou foi cota — e isso volta sozinho,
    # que é exatamente o que o `Retry-After` existe para dizer.
    resposta = _chat(monkeypatch, hermes_client.HermesFalhou("hermes_quota", 120))

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": "hermes_quota"}
    assert resposta.headers["Retry-After"] == "120"


def test_chat_quota_sem_retry_after_omite_o_header(monkeypatch):
    resposta = _chat(monkeypatch, hermes_client.HermesFalhou("hermes_quota"))

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": "hermes_quota"}
    assert "Retry-After" not in resposta.headers


def test_chat_credencial_consumida_e_503(monkeypatch):
    resposta = _chat(monkeypatch, hermes_client.HermesFalhou("hermes_credencial"))

    assert resposta.status_code == 503
    assert resposta.json() == {"detail": "hermes_credencial"}


def test_chat_falha_generica_continua_502(monkeypatch):
    # Contrato preservado: `test_capture_pipeline.py` depende deste 502.
    resposta = _chat(monkeypatch, RuntimeError("hermes_error"))

    assert resposta.status_code == 502
    assert resposta.json() == {"detail": "hermes_indisponivel"}


def test_chat_nao_vaza_o_texto_do_usuario_em_nenhum_codigo(monkeypatch):
    segredo = "conteudo-ultrassecreto-do-usuario"
    for exc in (
        hermes_client.HermesFalhou("hermes_quota", 60),
        hermes_client.HermesFalhou("hermes_credencial"),
        hermes_client.HermesFalhou("hermes_error"),
    ):
        resposta = _chat(monkeypatch, exc, texto=segredo)
        assert segredo not in resposta.text
