"""Escrita explícita no Google Calendar pessoal via API Calendar v3.

As URLs ICS continuam sendo a fronteira de leitura. Este módulo só escreve após um
POST autenticado do app e nunca registra refresh token, access token ou payload remoto.
"""

import base64
import hashlib
from datetime import date, datetime, time, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from .config import settings

TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"
TZ = ZoneInfo("America/Sao_Paulo")


class GoogleCalendarNotConfigured(RuntimeError):
    """Credenciais mínimas de escrita não foram configuradas."""


class GoogleCalendarUnavailable(RuntimeError):
    """OAuth ou Calendar API indisponível, sem carregar conteúdo remoto."""


class GoogleCalendarIdempotencyConflict(RuntimeError):
    """A mesma client_key foi apresentada com outro conteúdo."""


def _configured() -> bool:
    return all(
        (
            settings.google_calendar_client_id.strip(),
            settings.google_calendar_client_secret.strip(),
            settings.google_calendar_refresh_token.strip(),
            settings.google_calendar_id.strip(),
        )
    )


def event_id_for(client_key: str) -> str:
    """ID aceito pelo Google (base32hex lowercase), sem expor a chave do cliente."""
    digest = hashlib.sha256(client_key.encode("utf-8")).digest()
    encoded = base64.b32hexencode(digest).decode("ascii").lower().rstrip("=")
    return f"aeternum{encoded}"


async def create_event(
    titulo: str,
    data: str,
    hora: str,
    duracao_min: int,
    client_key: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    """Troca o refresh token e cria um evento; devolve só metadados necessários."""
    if not _configured():
        raise GoogleCalendarNotConfigured

    try:
        dia = date.fromisoformat(data)
        horario = time.fromisoformat(hora)
        inicio = datetime.combine(dia, horario, tzinfo=TZ)
        fim = inicio + timedelta(minutes=duracao_min)
        event_id = event_id_for(client_key)

        async with httpx.AsyncClient(
            timeout=settings.google_calendar_timeout,
            transport=transport,
        ) as client:
            token_response = await client.post(
                TOKEN_URL,
                data={
                    "client_id": settings.google_calendar_client_id,
                    "client_secret": settings.google_calendar_client_secret,
                    "refresh_token": settings.google_calendar_refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise GoogleCalendarUnavailable

            calendar_id = quote(settings.google_calendar_id, safe="")
            events_url = f"{CALENDAR_API}/calendars/{calendar_id}/events"
            event_response = await client.post(
                events_url,
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "id": event_id,
                    "summary": titulo,
                    "start": {
                        "dateTime": inicio.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                    "end": {
                        "dateTime": fim.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                },
            )
            reconciled = event_response.status_code == 409
            if reconciled:
                # Retry após perda de resposta: o ID determinístico já existe.
                event_response = await client.get(
                    f"{events_url}/{event_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            event_response.raise_for_status()
            remoto = event_response.json()
    except GoogleCalendarUnavailable:
        raise
    except (httpx.HTTPError, TypeError, ValueError):
        raise GoogleCalendarUnavailable from None

    if not isinstance(remoto, dict):
        raise GoogleCalendarUnavailable
    if reconciled:
        try:
            remote_start = datetime.fromisoformat(remoto["start"]["dateTime"])
            remote_end = datetime.fromisoformat(remoto["end"]["dateTime"])
        except (KeyError, TypeError, ValueError):
            raise GoogleCalendarUnavailable from None
        if (
            remoto.get("summary") != titulo
            or remote_start != inicio
            or remote_end != fim
        ):
            raise GoogleCalendarIdempotencyConflict
    remote_id = remoto.get("id")
    if not isinstance(remote_id, str) or not remote_id:
        raise GoogleCalendarUnavailable

    return {
        "id": remote_id,
        "titulo": str(remoto.get("summary") or titulo),
        "html_link": remoto.get("htmlLink"),
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat(),
        "fonte": "gcal",
    }
