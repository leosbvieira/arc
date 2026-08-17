import httpx
import pytest

from app import vault_client
from app.config import settings


def test_credenciais_reais_nao_sobrevivem():
    assert settings.github_pat == ""
    assert settings.clickup_token == ""
    assert settings.telegram_bot_token == ""
    assert settings.vault_repo == "testes/vault-que-nao-existe"


async def test_vault_falha_nomeado_em_vez_de_escrever():
    with pytest.raises(vault_client.VaultError, match="vault_nao_configurado"):
        await vault_client.write_raw("Raw/prova.md", "conteudo de teste")


async def test_socket_real_e_bloqueado():
    with pytest.raises(RuntimeError, match="rede_real_bloqueada_no_teste"):
        async with httpx.AsyncClient(timeout=5) as c:
            await c.get("https://api.github.com/zen")


def test_socket_real_sincrono_tambem():
    with pytest.raises(RuntimeError, match="rede_real_bloqueada_no_teste"):
        httpx.get("https://api.github.com/zen", timeout=5)
