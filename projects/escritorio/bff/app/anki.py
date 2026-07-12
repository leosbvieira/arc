"""Regras de serialização dos candidatos aprovados para o Anki."""


def tsv(cards: list[dict]) -> str:
    """Gera quatro colunas sem permitir que um campo quebre a grade do import."""
    linhas: list[str] = []

    for card in cards:
        campos: list[str] = []
        for nome in ("frente", "meaning", "example", "hook"):
            valor = card.get(nome, "")
            texto = "" if valor is None else str(valor)
            texto = (
                texto.replace("\r\n", " ")
                .replace("\r", " ")
                .replace("\n", " ")
                .replace("\t", " ")
            )
            campos.append(texto)

        linhas.append("\t".join(campos) + "\n")

    return "".join(linhas)
