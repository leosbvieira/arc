"""Composição da agenda operacional do dia."""

from datetime import date, datetime, time as _time, timedelta

from . import ics_client, store, tz

TZ = tz.TZ


def semana_iso(ref: date) -> str:
    """Produz a chave estável usada pelos temas da semana."""
    ano, semana, _ = ref.isocalendar()
    return f"{ano}-W{semana:02d}"


async def do_dia(ref: date, *, incluir_hora_marcada: bool = True) -> dict:
    """Junta calendário, tarefas com hora e temas sem ocultar o estado das fontes."""
    eventos, fontes = await ics_client.eventos_do_dia(ref)

    if incluir_hora_marcada:
        inicio = datetime.combine(ref, _time.min, tzinfo=TZ).timestamp()
        fim = datetime.combine(
            ref + timedelta(days=1),
            _time.min,
            tzinfo=TZ,
        ).timestamp()
        eventos.extend(
            {
                "hora": datetime.fromtimestamp(item["quando"], TZ).strftime("%H:%M"),
                "titulo": item["ref"],
                "fonte": "hora_marcada",
            }
            for item in store.schedules_between(inicio, fim)
        )

    eventos.sort(
        key=lambda evento: (
            evento["hora"] is not None,
            evento["hora"] or "",
            evento["titulo"],
        )
    )

    return {
        "data": ref.isoformat(),
        "eventos": eventos,
        "temas": store.list_temas(semana_iso(ref)),
        "fontes": fontes,
    }


def linhas_digest(ag: dict) -> list[str]:
    """Resume só o que existe; ausência de pauta não produz ruído, conforme a lei 4."""
    linhas: list[str] = []

    eventos = ag.get("eventos") or []
    if eventos:
        partes = [
            (
                f"{evento['hora']} {evento['titulo']}"
                if evento.get("hora")
                else f"dia inteiro: {evento['titulo']}"
            )
            for evento in eventos
        ]
        linhas.append(f"🗓️ {' · '.join(partes)}")

    temas = ag.get("temas") or []
    if temas:
        textos = [
            str(tema.get("texto", "")) if isinstance(tema, dict) else str(tema)
            for tema in temas
        ]
        textos = [texto for texto in textos if texto]
        if textos:
            linhas.append(f"📌 semana: {' · '.join(textos)}")

    return linhas
