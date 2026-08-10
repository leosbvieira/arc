"""Regras de serialização dos candidatos aprovados para o Anki."""

DECK_PAI = "Leitura"
_CAMPOS = ("frente", "meaning", "example", "hook", "deck")


def deck_para_livro(titulo: str) -> str:
    """Subdeck da obra sob um pai fixo.

    Estudar `Leitura` puxa de todas as obras; `Leitura::Sapiens` puxa de uma. O `::`
    é o separador de subdeck do Anki, então um título que o contenha viraria uma
    árvore acidental — trocamos por hífen.
    """
    limpo = " ".join(titulo.replace("::", "-").split())
    return f"{DECK_PAI}::{limpo}" if limpo else ""


def tsv(cards: list[dict]) -> str:
    """Cinco colunas sem permitir que um campo quebre a grade do import.

    O deck vai por LINHA (`#deck column:5`), e não por arquivo: um export carrega
    cards de obras diferentes.

    Célula de deck vazia NUNCA é emitida — card sem obra cai no deck-pai. O banco
    guarda '' porque é o que o sistema sabe; o fallback é decisão de serialização e
    mora aqui. Assim não dependemos do que o Anki faria com uma célula vazia.
    """
    linhas: list[str] = ["#separator:tab\n", "#html:false\n", "#deck column:5\n"]

    for card in cards:
        campos: list[str] = []
        for nome in _CAMPOS:
            valor = card.get(nome, "")
            texto = "" if valor is None else str(valor)
            texto = (
                texto.replace("\r\n", " ")
                .replace("\r", " ")
                .replace("\n", " ")
                .replace("\t", " ")
            )
            campos.append(texto)

        if not campos[-1].strip():
            campos[-1] = DECK_PAI

        linhas.append("\t".join(campos) + "\n")

    return "".join(linhas)
