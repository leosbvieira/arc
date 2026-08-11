"""Template da tarefa de resumão que nasce quando o Leo termina uma obra.

Ele pediu isto na conversa que originou a estante: *"ao finalizar, fazer um resumão
de todas [as sessões] — mas aí não precisa ter no app, no máximo uma tarefa para eu
fazer isso, com aprendizados etc. Com template obviamente"*.

Puro de propósito: sem rede, sem relógio, sem banco. Recebe as sessões já lidas e
devolve nome e descrição — assim dá para testar o texto sem subir ClickUp nenhum.

**Lei 7 não se aplica ao conteúdo aqui**: o título da obra é o ponto da tarefa, e
a tarefa vive no ClickUp do Leo, que é área dele. O que NÃO entra é o texto das
notas: a descrição aponta para os arquivos do vault, não os copia.
"""

from datetime import date, datetime

from .tz import TZ

MARKER_PREFIX = "book-summary"


def marker(book_id: int, ciclo: int) -> str:
    """Primeira linha da descrição, para reencontrar a tarefa por busca.

    Mesmo mecanismo do `[cap:id]` da captura (`capture_pipeline.py`), pela mesma
    razão: o POST do ClickUp não é idempotente, então a única forma de saber se a
    tarefa foi criada quando a resposta se perdeu é procurá-la pelo conteúdo.
    """
    return f"[{MARKER_PREFIX}:{book_id}:{ciclo}]"


def _dia(ts: float | None) -> date | None:
    return None if ts is None else datetime.fromtimestamp(ts, TZ).date()


def faixa_de_paginas(inicial: int | None, final: int | None) -> str:
    """Os quatro formatos, iguais aos do frontmatter: os dois, só um, ou nenhum.

    Inventar o limite que falta seria escrever no ClickUp um número que ele nunca
    disse — e é justamente o campo que ele usa para saber onde parou.
    """
    if inicial is not None and final is not None:
        return f"p. {inicial}–{final}"
    if inicial is not None:
        return f"a partir da p. {inicial}"
    if final is not None:
        return f"até a p. {final}"
    return "sem página registrada"


def agregado_de_paginas(sessoes: list[dict]) -> str:
    """A faixa da leitura inteira. Usa o menor início e o maior fim REGISTRADOS."""
    inicios = [s["pagina_inicial"] for s in sessoes if s.get("pagina_inicial") is not None]
    finais = [s["pagina_final"] for s in sessoes if s.get("pagina_final") is not None]
    return faixa_de_paginas(min(inicios) if inicios else None, max(finais) if finais else None)


def nome(titulo: str, ciclo: int) -> str:
    """`ciclo` só aparece a partir da 2ª leitura: 'leitura 1' na primeira seria ruído."""
    sufixo = "" if ciclo <= 1 else f" (leitura {ciclo})"
    return f"Resumão: {titulo}{sufixo}"


def descricao(*, titulo: str, book_id: int, ciclo: int, sessoes: list[dict]) -> str:
    """O corpo da tarefa: o que ele já registrou, e o que falta ele escrever.

    As perguntas vêm depois dos fatos de propósito. Abrir com o formulário vazio
    faz a tarefa parecer trabalho; abrir com as sessões que ele de fato leu faz
    ela parecer a continuação de algo.
    """
    dias = [d for d in (_dia(s.get("compiled_at")) for s in sessoes) if d is not None]
    linhas = [marker(book_id, ciclo), "", f"# {titulo}", ""]

    if dias:
        primeira, ultima = min(dias), max(dias)
        periodo = (
            primeira.isoformat()
            if primeira == ultima
            else f"{primeira.isoformat()} a {ultima.isoformat()}"
        )
        linhas.append(f"{len(sessoes)} sessão(ões) · {periodo} · {agregado_de_paginas(sessoes)}")
    else:
        linhas.append(f"{len(sessoes)} sessão(ões) · {agregado_de_paginas(sessoes)}")
    linhas.append("")

    linhas.append("## Sessões")
    for sessao in sessoes:
        dia = _dia(sessao.get("compiled_at"))
        partes = [dia.isoformat() if dia else "sem data"]
        partes.append(faixa_de_paginas(sessao.get("pagina_inicial"), sessao.get("pagina_final")))
        caminho = sessao.get("vault_path")
        # O caminho do vault é neutro por desenho (lei 7) — não diz o que ele leu.
        # Levá-lo é o que torna o resumão fazível sem reabrir o app.
        if caminho:
            partes.append(caminho)
        linhas.append("- " + " · ".join(partes))
    linhas.append("")

    linhas.extend(
        [
            "## O que fica",
            "",
            "**A tese, em uma frase:**",
            "",
            "**O que muda no que eu faço:**",
            "",
            "**O que eu discordo:**",
            "",
            "**Vale virar card:**",
            "",
        ]
    )
    return "\n".join(linhas)
