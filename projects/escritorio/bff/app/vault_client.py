"""Escrita deterministica no vault (GitHub Contents API). O BFF segura a caneta; LLM so propoe.
Regras: verbatim (lei 3), paths/commits neutros (lei 7), retry de SHA, dedupe por marker."""
import base64
from datetime import datetime

import httpx

from .config import settings

RAW_DIR = "1- Inbox/Raw"
_SHA_RETRIES = 3


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
        r = await c.get(_url(path), params={"ref": settings.vault_branch})
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise VaultError(f"GET {path}: {r.status_code}")
    return r.json()


async def _put(path: str, content: str, message: str, sha: str | None) -> str:
    body = {"message": message, "branch": settings.vault_branch,
            "content": base64.b64encode(content.encode("utf-8")).decode()}
    if sha:
        body["sha"] = sha
    async with _client() as c:
        r = await c.put(_url(path), json=body)
    if r.status_code in (409, 422):
        raise _ShaConflict()
    if r.status_code not in (200, 201):
        raise VaultError(f"PUT {path}: {r.status_code}")
    return path


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


async def append_file(path: str, block: str, message: str,
                      header_if_new: str = "", dedupe_marker: str | None = None) -> str:
    for _ in range(_SHA_RETRIES):
        existing = await _get(path)
        if existing:
            current = base64.b64decode(existing["content"]).decode("utf-8")
            if dedupe_marker and dedupe_marker in current:
                return path                                   # ja gravado (retry idempotente)
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
    d = datetime.fromtimestamp(ts) if ts else datetime.now()
    path = f"{RAW_DIR}/{d:%Y-%m-%d} - raw-c{capture_id}.md"
    existing = await _get(path)
    if existing:                                              # ja gravado => idempotente
        return path
    return await put_file(path, text, f"raw: c{capture_id}")
