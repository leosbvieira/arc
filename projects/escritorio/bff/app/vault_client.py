"""Escrita deterministica no vault (GitHub Contents API). O BFF segura a caneta; LLM so propoe.
Regras: verbatim (lei 3), paths/commits neutros (lei 7), retry de SHA, dedupe por marker."""
import asyncio
import base64
import hashlib
from datetime import datetime

import httpx

from .config import settings
from .tz import TZ

RAW_DIR = "1- Inbox/Raw"
READING_DIR = "Leituras"
_SHA_RETRIES = 3
_TRANSIENT_RETRIES = 3


class VaultError(RuntimeError):
    pass


def _client() -> httpx.AsyncClient:
    if not settings.github_pat:
        # fail-fast nomeado: sem PAT o httpx falharia com LocalProtocolError opaco
        raise VaultError("vault_nao_configurado")
    return httpx.AsyncClient(
        base_url="https://api.github.com",
        headers={"Authorization": f"Bearer {settings.github_pat}",
                 "Accept": "application/vnd.github+json"},
        timeout=30,
    )


def _url(path: str) -> str:
    return f"/repos/{settings.vault_repo}/contents/{path}"


async def _get(path: str) -> dict | None:
    async with _client() as c:
        for attempt in range(_TRANSIENT_RETRIES):
            try:
                r = await c.get(
                    _url(path),
                    params={"ref": settings.vault_branch},
                )
            except httpx.TransportError as exc:
                if attempt == _TRANSIENT_RETRIES - 1:
                    raise VaultError(
                        f"GET {path}: {type(exc).__name__}"
                    ) from exc
                await asyncio.sleep(1)
                continue

            if r.status_code == 404:
                return None
            if r.status_code == 200:
                return r.json()
            if r.status_code >= 500:
                if attempt == _TRANSIENT_RETRIES - 1:
                    raise VaultError(f"GET {path}: {r.status_code}")
                await asyncio.sleep(1)
                continue
            raise VaultError(f"GET {path}: {r.status_code}")

    raise AssertionError("retry GET sem desfecho")


async def _put(path: str, content: str, message: str, sha: str | None) -> str:
    body = {"message": message, "branch": settings.vault_branch,
            "content": base64.b64encode(content.encode("utf-8")).decode()}
    if sha:
        body["sha"] = sha

    async with _client() as c:
        for attempt in range(_TRANSIENT_RETRIES):
            try:
                r = await c.put(_url(path), json=body)
            except httpx.TransportError as exc:
                if attempt == _TRANSIENT_RETRIES - 1:
                    raise VaultError(
                        f"PUT {path}: {type(exc).__name__}"
                    ) from exc
                await asyncio.sleep(1)
                continue

            if r.status_code in (409, 422):
                raise _ShaConflict()
            if r.status_code in (200, 201):
                return path
            if r.status_code >= 500:
                if attempt == _TRANSIENT_RETRIES - 1:
                    raise VaultError(f"PUT {path}: {r.status_code}")
                await asyncio.sleep(1)
                continue
            raise VaultError(f"PUT {path}: {r.status_code}")

    raise AssertionError("retry PUT sem desfecho")


class _ShaConflict(Exception):
    pass


async def put_file(path: str, content: str, message: str) -> str:
    for _ in range(_SHA_RETRIES):
        existing = await _get(path)
        try:
            return await _put(path, content, message, existing["sha"] if existing else None)
        except _ShaConflict:
            continue
    raise VaultError(f"PUT {path}: conflito de SHA persistente")


def substituir_bloco(current: str, marker: str, block: str) -> str:
    """Troca o bloco marcado por `marker` pelo `block` novo, no lugar.

    O bloco vai da linha que carrega o marker ate a proxima linha que comeca com
    "## " (ou o fim do arquivo). Existe para o caso de reaprovar o fechamento com o
    texto corrigido: sem isto, o dedupe por dia devolvia sucesso e DESCARTAVA a
    correcao em silencio -- pior que o bug que ele consertou, porque o app ainda
    apagava o rascunho local achando que tinha gravado.
    """
    linhas = current.split("\n")
    inicio = next((i for i, l in enumerate(linhas) if marker in l), None)
    if inicio is None:
        return current.rstrip("\n") + "\n\n" + block
    fim = len(linhas)
    for j in range(inicio + 1, len(linhas)):
        if linhas[j].startswith("## "):
            fim = j
            break
    novas = linhas[:inicio] + block.rstrip("\n").split("\n") + [""] + linhas[fim:]
    return "\n".join(novas).rstrip("\n") + "\n"


async def append_file(path: str, block: str, message: str,
                      header_if_new: str = "", dedupe_marker: str | None = None,
                      substituir_marcado: bool = False) -> str:
    for _ in range(_SHA_RETRIES):
        existing = await _get(path)
        if existing:
            current = base64.b64decode(existing["content"]).decode("utf-8")
            if dedupe_marker and dedupe_marker in current:
                if not substituir_marcado:
                    return path                               # ja gravado (retry idempotente)
                new = substituir_bloco(current, dedupe_marker, block)
                if new == current:
                    return path                               # nada mudou: nao gasta commit
            else:
                new = current.rstrip("\n") + "\n\n" + block
        else:
            new = (header_if_new + "\n\n" if header_if_new else "") + block
        try:
            return await _put(path, new, message, existing["sha"] if existing else None)
        except _ShaConflict:
            continue
    raise VaultError(f"PUT {path}: conflito de SHA persistente")


async def write_raw(text: str, capture_id: int | str, ts: float | None = None) -> str:
    """Grava o texto EXATO. Path/commit neutros e DETERMINISTICOS: id + data do EVENTO.
    A data vem do ts de origem (enfileiramento), nao do relogio do retry =>
    crash/retry em qualquer momento (inclusive cruzando meia-noite) produz o MESMO path."""
    # Fuso do Leo, não do processo. Este módulo é o que NOMEIA arquivo, e era o único
    # produtor de data que nunca migrou para `tz.TZ` (`resumo_obra.py` já fazia certo).
    # Num host em UTC — o VPS é o próximo passo declarado — uma captura das 22h BRT
    # arquiva em D+1 enquanto a Daily que a referencia é D.
    d = datetime.fromtimestamp(ts, TZ) if ts else datetime.now(TZ)
    path = f"{RAW_DIR}/{d:%Y-%m-%d} - raw-c{capture_id}.md"
    existing = await _get(path)
    if existing:                                              # ja gravado => idempotente
        return path
    return await put_file(path, text, f"raw: c{capture_id}")


async def write_reading_note(
    markdown: str,
    reading_id: int,
    *,
    ts: float,
    client_key: str,
) -> str:
    """Publica uma vez em caminho neutro/determinístico; retry não cria outro commit."""
    d = datetime.fromtimestamp(ts, TZ)  # fuso do Leo: ver write_raw
    key_hash = hashlib.sha256(client_key.encode("utf-8")).hexdigest()[:10]
    path = (
        f"{READING_DIR}/{d:%Y-%m-%d} - "
        f"leitura-r{reading_id}-{key_hash}.md"
    )
    existing = await _get(path)
    if existing:
        return path
    return await put_file(path, markdown, f"leitura: r{reading_id}")
