import httpx
import pytest

from app import vault_client


@pytest.fixture(autouse=True)
def sem_espera_de_retry(monkeypatch):
    async def sleep_imediato(_delay):
        return None

    monkeypatch.setattr(vault_client.asyncio, "sleep", sleep_imediato)


def configurar_client_mock(monkeypatch, sequencia):
    chamadas = []

    async def handler(request):
        indice = len(chamadas)
        chamadas.append(request)
        resultado = sequencia[indice]

        if isinstance(resultado, Exception):
            raise resultado

        status, json = resultado
        return httpx.Response(status, json=json)

    transport = httpx.MockTransport(handler)

    def client_factory():
        return httpx.AsyncClient(
            transport=transport,
            base_url="https://api.github.com",
        )

    monkeypatch.setattr(vault_client, "_client", client_factory)
    return chamadas


async def test_get_retenta_502_e_retorna_json(monkeypatch):
    esperado = {"sha": "abc", "content": "dGVzdGU="}
    chamadas = configurar_client_mock(
        monkeypatch,
        [(502, {}), (200, esperado)],
    )

    resultado = await vault_client._get("arquivo.md")

    assert resultado == esperado
    assert len(chamadas) == 2


async def test_get_esgota_tres_tentativas_502(monkeypatch):
    chamadas = configurar_client_mock(
        monkeypatch,
        [(502, {}), (502, {}), (502, {})],
    )

    with pytest.raises(vault_client.VaultError, match="502"):
        await vault_client._get("arquivo.md")

    assert len(chamadas) == 3


async def test_get_404_retorna_none_sem_retry(monkeypatch):
    chamadas = configurar_client_mock(
        monkeypatch,
        [(404, {})],
    )

    resultado = await vault_client._get("ausente.md")

    assert resultado is None
    assert len(chamadas) == 1


async def test_put_409_gera_conflito_sem_retry(monkeypatch):
    chamadas = configurar_client_mock(
        monkeypatch,
        [(409, {})],
    )

    with pytest.raises(vault_client._ShaConflict):
        await vault_client._put(
            "arquivo.md",
            "conteudo",
            "mensagem",
            "sha-anterior",
        )

    assert len(chamadas) == 1


async def test_get_retenta_connect_timeout_e_retorna_json(monkeypatch):
    esperado = {"sha": "abc", "content": "dGVzdGU="}
    chamadas = configurar_client_mock(
        monkeypatch,
        [
            httpx.ConnectTimeout("t"),
            httpx.ConnectTimeout("t"),
            (200, esperado),
        ],
    )

    resultado = await vault_client._get("arquivo.md")

    assert resultado == esperado
    assert len(chamadas) == 3
