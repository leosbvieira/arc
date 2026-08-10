"""Frontmatter da nota de leitura: escrito por CÓDIGO, dentro do portão humano.

Entra em /draft, antes do staging, e não depois da aprovação. Colar frontmatter na
hora de gravar no vault publicaria um documento diferente do que o Leo aprovou e
tornaria o `source_digest` uma garantia falsa.

Sem PyYAML de propósito (o BFF não tem a dependência e não vale acrescentar por três
linhas): só `livro` é texto livre, e ele sai sempre como escalar entre aspas duplas.
"""

import unicodedata
from datetime import datetime

# Versão do formato do draft. Draft gravado antes desta versão não é reusado nem
# publicado: é regenerado com frontmatter e volta ao preview para nova aprovação.
DRAFT_FMT = 2


def yaml_escalar(valor: str) -> str:
    """Escalar entre aspas duplas, sempre.

    Aspas incondicionais resolvem de uma vez `:`, `#`, `---` e os títulos que o YAML
    interpretaria como outro tipo (`yes`, `123`). A ordem dos replaces importa: a
    barra primeiro, senão o escape das aspas seria escapado de novo.
    """
    limpo = "".join(
        " " if unicodedata.category(c).startswith("C") else c for c in valor
    )
    limpo = limpo.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{limpo}"'


def frontmatter(
    *,
    livro: str,
    pagina_inicial: int | None,
    pagina_final: int | None,
    inicio: float,
) -> str:
    """Bloco YAML + linha em branco, pronto para prefixar a nota do Hermes.

    `paginas` só existe quando os DOIS limites existem. Os outros três estados
    omitem a chave — não há `paginas: -42` nem `paginas: null`.
    """
    linhas = ["---", f"livro: {yaml_escalar(livro)}"]
    if pagina_inicial is not None and pagina_final is not None:
        linhas.append(f"paginas: {pagina_inicial}-{pagina_final}")
    linhas.append(f"data: {datetime.fromtimestamp(inicio):%Y-%m-%d}")
    linhas.append("---")
    return "\n".join(linhas) + "\n\n"
