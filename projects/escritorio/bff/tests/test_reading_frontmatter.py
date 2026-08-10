from app.reading_frontmatter import DRAFT_FMT, frontmatter, yaml_escalar


def test_draft_fmt_e_dois():
    assert DRAFT_FMT == 2


def test_escalar_sempre_entre_aspas():
    # Aspas sempre presentes resolvem de uma vez `:`, `#`, `---`, e títulos que o
    # YAML leria como outro tipo.
    assert yaml_escalar("Sapiens") == '"Sapiens"'
    assert yaml_escalar("yes") == '"yes"'
    assert yaml_escalar("123") == '"123"'


def test_escalar_escapa_barra_e_aspas():
    assert yaml_escalar('diz "oi"') == '"diz \\"oi\\""'
    assert yaml_escalar("c:\\livros") == '"c:\\\\livros"'


def test_escalar_colapsa_controle_e_quebra_de_linha():
    assert yaml_escalar("uma\nlinha") == '"uma linha"'
    assert yaml_escalar("com\ttab") == '"com tab"'
    assert "\n" not in yaml_escalar("---\n---")


def test_frontmatter_completo():
    saida = frontmatter(
        livro="Sapiens", pagina_inicial=190, pagina_final=214, inicio=1_754_697_600.0
    )
    assert saida.startswith("---\n")
    assert 'livro: "Sapiens"' in saida
    assert "paginas: 190-214" in saida
    assert saida.endswith("---\n\n")


def test_paginas_so_aparece_com_os_dois_limites():
    combinacoes = [
        (190, None),
        (None, 214),
        (None, None),
    ]
    for inicial, final in combinacoes:
        saida = frontmatter(
            livro="Sapiens",
            pagina_inicial=inicial,
            pagina_final=final,
            inicio=1_754_697_600.0,
        )
        assert "paginas" not in saida
        assert "null" not in saida


def test_titulo_com_dois_pontos_nao_quebra_o_yaml():
    saida = frontmatter(
        livro="Sapiens: uma breve história",
        pagina_inicial=None,
        pagina_final=None,
        inicio=1_754_697_600.0,
    )
    # Uma linha só para o título; nenhuma chave nova foi injetada.
    corpo = [linha for linha in saida.splitlines() if linha and linha != "---"]
    assert len(corpo) == 2  # livro + data
