"""Uma conversa com o Hermes por vez.

Cada `_oneshot` sobe um processo `hermes.exe` com timeout de 150s. São 7 pontos de
chamada (chat, captura, triagem, leitura, anki, diário, review) e não havia trava
nenhuma: o worker de captura, a tela Hoje e o Chat competiam pela mesma CLI. Dois
processos do agente ao mesmo tempo brigam por memória/sessão e ambos ficam lentos.
"""
import asyncio
from types import SimpleNamespace

from app import hermes_client
import pytest

from app.config import settings

# Estes testes SÃO sobre o `_oneshot`; a trava do conftest o substituiria.
pytestmark = pytest.mark.hermes_oneshot


async def test_chamadas_do_hermes_nao_se_atropelam(monkeypatch):
    monkeypatch.setattr(settings, "hermes_mock", False)
    simultaneos = 0
    pico = 0

    async def fake_to_thread(fn, *a, **kw):
        nonlocal simultaneos, pico
        simultaneos += 1
        pico = max(pico, simultaneos)
        await asyncio.sleep(0.05)
        simultaneos -= 1
        return SimpleNamespace(returncode=0, stdout="ok")

    monkeypatch.setattr(hermes_client.asyncio, "to_thread", fake_to_thread)

    await asyncio.gather(*[hermes_client._oneshot(f"p{i}") for i in range(5)])

    assert pico == 1, f"até {pico} processos do Hermes ao mesmo tempo"
