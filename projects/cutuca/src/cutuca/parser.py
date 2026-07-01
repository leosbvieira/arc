"""The ONE model seam (SPEC FR-3). `parse_task` turns free text into structured
fields via a single Messages API call to Haiku. Swapping model or testing means
touching only this file. The client is injectable so tests never hit the network.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Callable, Optional

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# Strict-JSON contract. No markdown, no preamble — parseable by json.loads.
SYSTEM_PROMPT = """Você extrai UMA tarefa de trabalho a partir de uma mensagem solta em português.
Responda APENAS com um objeto JSON válido, sem markdown, sem crases, sem texto antes ou depois.

Formato exato:
{"assignee": <string ou null>, "titulo": <string>, "prazo_iso": <"YYYY-MM-DD" ou null>, "lista": <string ou null>}

Regras:
- "assignee": o nome da pessoa responsável, se mencionado; senão null.
- "titulo": descrição curta e clara da tarefa (imperativo). Sempre preencha.
- "prazo_iso": a data limite em YYYY-MM-DD. Converta expressões relativas ("hoje",
  "amanhã", "sexta", "em 3 dias") usando a data de hoje fornecida. Se não houver prazo, null.
- "lista": nome de lista/projeto se citado; senão null.
- Nunca invente assignee ou prazo. Se não estiver na mensagem, use null."""

# Fields whose absence should trigger an ask-back rather than task creation.
REQUIRED_FOR_CREATE = ("assignee", "prazo_iso")


class ParseError(Exception):
    """Raised on unrecoverable model/transport failure (caller should ask back)."""


def _default_client():
    """Lazy real client so importing this module needs no anthropic install/key."""
    import os

    import anthropic

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ParseError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=key)


def _response_text(resp: Any) -> str:
    """Concatenate text blocks from an anthropic Messages response."""
    content = getattr(resp, "content", None)
    if content is None and isinstance(resp, dict):
        content = resp.get("content")
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content or []:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if text:
            parts.append(text)
    return "".join(parts)


def _extract_json(raw: str) -> Optional[dict]:
    """json.loads inside try/except; defensively strip fences / find the object."""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
        text = text.strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            return obj if isinstance(obj, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _valid_iso(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        return None


def _normalize(data: dict) -> Optional[dict]:
    titulo = _clean(data.get("titulo"))
    if not titulo:
        return None  # a task with no title is not a task
    return {
        "assignee": _clean(data.get("assignee")),
        "titulo": titulo,
        "prazo_iso": _valid_iso(_clean(data.get("prazo_iso"))),
        "lista": _clean(data.get("lista")),
    }


def missing_fields(parsed: Optional[dict]) -> list[str]:
    """Which create-required fields are absent. Empty list == ready to create."""
    if parsed is None:
        return list(REQUIRED_FOR_CREATE)
    return [f for f in REQUIRED_FOR_CREATE if not parsed.get(f)]


def parse_task(
    text: str,
    client: Any = None,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 400,
    today: Optional[date] = None,
    timeout: Optional[float] = 20,
) -> Optional[dict]:
    """Free text -> {assignee, titulo, prazo_iso, lista} or None.

    None means "could not parse a task" (unparseable model output or no title) —
    the caller should ask back. A returned dict may still have null assignee/prazo;
    `missing_fields` decides whether it is complete enough to create.

    `client` may be any object exposing ``messages.create(...)`` (real anthropic
    client or a test fake). If omitted, a real client is built lazily.
    """
    if not text or not text.strip():
        return None

    client = client or _default_client()
    today = today or date.today()

    user_msg = f"Data de hoje: {today.isoformat()}\n\nMensagem:\n{text.strip()}"

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_msg}],
    }
    try:
        create: Callable = client.messages.create
        try:
            resp = create(timeout=timeout, **kwargs)
        except TypeError:
            resp = create(**kwargs)  # fakes/clients that don't accept timeout
    except Exception as exc:  # transport / API failure
        raise ParseError(str(exc)) from exc

    raw = _response_text(resp)
    data = _extract_json(raw)
    if data is None:
        return None
    return _normalize(data)
