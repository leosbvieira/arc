"""O fuso do Leo, em um lugar só.

`ZoneInfo("America/Sao_Paulo")` estava definido em 11 pontos do BFF. O comentário
em `hermes_client.py` já pedia a extração ("se virar um 3º uso, extrair pra um
app/tz.py comum") — e o custo de não ter feito foi concreto: `store.py` gravava
`notif_log.data_local` com `date.today()`, o relógio do PROCESSO, porque não podia
importar `pontos.hoje_local()` (`pontos` importa `store`, daria ciclo).

Este módulo não importa nada do app, então qualquer um pode importá-lo.

Por que importa agora: no VPS em UTC — o próximo passo declarado — das 21h à
meia-noite BRT o servidor já está em D+1. Os ritos da noite gravariam no dia
seguinte, e o dedupe de notificação não encontraria o envio do dia: o aviso sairia
duas vezes, e o dia vivido ficaria sem linha.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")


def agora_local() -> datetime:
    return datetime.now(TZ)


def hoje_local() -> date:
    """A data que o Leo diria se você perguntasse — nunca a do processo."""
    return datetime.now(TZ).date()
