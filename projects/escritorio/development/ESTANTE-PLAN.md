# Estante (fatia 1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o app saber quais obras o Leo está lendo e em que página cada uma parou, e fazer os cards do Anki nascerem no deck da obra.

**Architecture:** Uma tabela `books` mínima (título, slug, status, ciclo) vira a identidade da obra. `reading_sessions` ganha `book_id` e `book_ciclo` copiados na criação, mais `compiled_at` carimbado pelo servidor. Progresso não é coluna: é derivado da sessão compilada mais recente do ciclo. O título canônico entra no frontmatter da nota **antes** do staging, para que o publicado continue byte-a-byte igual ao aprovado.

**Tech Stack:** FastAPI + SQLite (`bff/`), React Native/Expo + TypeScript (`app/`). Testes: `pytest` no BFF, `node --test` com type-stripping nativo no app.

## Global Constraints

- **Lei 3 (portão humano):** o sistema propõe, o Leo aprova. Nada é publicado sem aprovação explícita.
- **Lei 7 (neutralidade):** paths e mensagens de commit no vault não revelam conteúdo. Esta fatia **não altera** `vault_client.write_reading_note` nem a mensagem de commit.
- **Fidelidade:** o que vai para o vault é `draft_md` byte-a-byte. Nada é concatenado depois da aprovação.
- **Sem dependência nova:** o BFF não tem PyYAML (`bff/requirements.txt`) e não ganha nenhuma biblioteca nesta fatia.
- **Sem backfill:** linhas antigas de `reading_sessions` ficam com `book_id`, `book_ciclo`, `compiled_at` e `draft_fmt` todos `NULL`. Nenhuma migração de dado, só de schema.
- **Caminho antigo intacto:** `POST /reading/sessions` sem `book_id` mantém exatamente o comportamento de hoje. Os testes de leitura existentes (`test_reading_buffer.py`, `test_reading_staging.py`, `test_reading_reconcile.py`, `test_reading_tail_mutations.py`) devem passar sem edição.
- **Spec de referência:** `development/ESTANTE-SPEC.md` (revisão 4). Fatias 2 (ClickUp) e 3 (recap) estão fora deste plano.
- Rodar os testes do BFF de dentro de `projects/escritorio/bff/`: `.venv/Scripts/python -m pytest`. **O `python` puro não serve** — resolve para o venv do Hermes, que não tem pytest instalado.
- Rodar os testes do app de dentro de `projects/escritorio/app/`: `npm run check`.

---

## File Structure

**Criar (BFF):**
- `bff/app/reading_frontmatter.py` — serialização segura do frontmatter YAML. Responsabilidade única: transformar (livro, páginas, data) em texto. Sem I/O, sem banco.
- `bff/tests/test_books.py` — obra, slug, ciclo, terminar/reabrir, derivadas.
- `bff/tests/test_reading_frontmatter.py` — escapes YAML e as quatro combinações de página.
- `bff/tests/test_estante_sessao.py` — sessão com `book_id`, deck, `draft_fmt`.

**Modificar (BFF):**
- `bff/app/store.py` — schema de `books`, migrações, `slug_livro`, CRUD de obra, derivadas, `book_id`/`book_ciclo` em `create_reading_session`, `compiled_at` em `finish_reading_compile`, `deck` em `_insert_anki_cards`/`finish_anki_suggestion`/`add_anki_cards`.
- `bff/app/main.py` — quatro endpoints de obra, `book_id` no modelo de sessão, frontmatter em `/draft`, guarda de `draft_fmt` em `/compile`, deck em `_suggest_anki_once` e `/anki/sugerir`.
- `bff/app/anki.py` — `deck_para_livro` e a coluna de deck no TSV.

**Criar (app):**
- `app/src/shelfView.ts` — módulo puro: transforma a resposta da API na linha que a tela desenha. Segue o padrão de `mesaView.ts`/`homeAction.ts`: sem import de valor, relógio por parâmetro.
- `app/tests/shelfView.test.mjs`.

**Modificar (app):**
- `app/src/readingApi.ts` — tipo `Book` e as quatro chamadas de obra. Mesmo `request()` privado, mesma responsabilidade (a API da lane Leitura).
- `app/src/readingDraft.ts` — `bookId` no `ReadingDraft`.
- `app/src/screens/Capture.tsx` — a estante no lugar do campo livre, `✓` para terminar, lista de terminadas.

---

### Task 1: (resolvida antes do plano começar)

O portão do TSV era: `#deck column:N` funciona na versão de Anki do Leo?

**Resolvido:** o Anki do Leo é de 2026, e o header existe desde a 2.1.55 (fim de 2022). O caminho é **um arquivo só, com deck por linha**. A Task 8 implementa essa forma; a bifurcação "um arquivo por deck" foi descartada.

Sobrava uma segunda incerteza — em que deck cai uma célula de deck **vazia**, já que os cards antigos têm `deck=''`. Ela foi resolvida por desenho, não por teste: **o TSV nunca emite célula vazia**. Card sem obra sai no deck-pai `Leitura`. Isso remove a pergunta em vez de respondê-la, e o comportamento resultante é o certo de qualquer forma — um card de leitura sem obra ainda é um card de leitura.

O banco continua guardando `''` para card sem obra: o `deck` gravado diz o que o sistema sabe, e o fallback é uma decisão de **serialização**, que mora no `anki.py`. Não misturar as duas coisas é o que permite, na fatia 2, reclassificar cards antigos se algum dia valer a pena.

Nada a implementar aqui. Seguir para a Task 2.

---

### Task 2: Tabela `books`, migração e slug

**Files:**
- Modify: `bff/app/store.py` (bloco de schema em `_SCHEMA`, migrações em `init_db` perto de `store.py:277`, funções novas depois de `list_sessions_since`)
- Test: `bff/tests/test_books.py`

**Interfaces:**
- Produces:
  - `store.slug_livro(titulo: str) -> str`
  - `store.create_book(titulo: str) -> tuple[dict, bool]` — levanta `ValueError("titulo_invalido")` se o slug sair vazio
  - `store.get_book(book_id: int) -> dict | None`

- [ ] **Step 1: Escrever os testes que falham**

Criar `bff/tests/test_books.py`:

```python
import pytest

from app import store
from app.config import settings


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    return None


def test_slug_normaliza_caixa_acento_e_espaco(db):
    assert store.slug_livro("Sapiens") == store.slug_livro("sapiens ")
    assert store.slug_livro("Antifrágil") == store.slug_livro("ANTIFRAGIL")
    assert store.slug_livro("  dois   espaços  ") == "dois espacos"


def test_slug_preserva_pontuacao(db):
    # Descartar pontuação colapsaria estas três obras numa só.
    slugs = {store.slug_livro("C"), store.slug_livro("C++"), store.slug_livro("C#")}
    assert len(slugs) == 3


def test_slug_vazio_e_recusado(db):
    for titulo in ("", "   ", "\n\t", "\x00"):
        with pytest.raises(ValueError, match="titulo_invalido"):
            store.create_book(titulo)


def test_create_book_reusa_a_obra_de_mesmo_slug(db):
    primeira, criada = store.create_book("Sapiens")
    assert criada is True
    assert primeira["status"] == "lendo"
    assert primeira["ciclo"] == 1

    segunda, criada_de_novo = store.create_book("sapiens ")
    assert criada_de_novo is False
    assert segunda["id"] == primeira["id"]
    # O título guardado é o da primeira criação; a segunda não reescreve.
    assert segunda["titulo"] == "Sapiens"


def test_get_book(db):
    criada, _ = store.create_book("Antifrágil")
    assert store.get_book(criada["id"])["titulo"] == "Antifrágil"
    assert store.get_book(9999) is None


def test_migracao_e_idempotente(db):
    store.init_db()
    store.init_db()
    criada, _ = store.create_book("Sapiens")
    assert criada["id"] > 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_books.py -v`
Expected: FAIL com `AttributeError: module 'app.store' has no attribute 'slug_livro'`

- [ ] **Step 3: Acrescentar a tabela ao schema**

Em `bff/app/store.py`, na string de schema, logo depois do bloco `CREATE TABLE IF NOT EXISTS reading_buffer (...)` (perto de `store.py:111`):

```sql
CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  titulo TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'lendo',
  ciclo INTEGER NOT NULL DEFAULT 1,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
```

- [ ] **Step 4: Acrescentar as migrações condicionais**

Em `init_db`, logo depois do bloco `if "proxima_em" not in fila_columns:` (perto de `store.py:288`), seguindo o mesmo padrão:

```python
        reading_columns = {
            row["name"] for row in con.execute("PRAGMA table_info(reading_sessions)")
        }
        for coluna, tipo in (
            ("book_id", "INTEGER"),
            ("book_ciclo", "INTEGER"),
            ("compiled_at", "REAL"),
            ("draft_fmt", "INTEGER"),
        ):
            if coluna not in reading_columns:
                con.execute(f"ALTER TABLE reading_sessions ADD COLUMN {coluna} {tipo}")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_reading_sessions_book "
            "ON reading_sessions(book_id, book_ciclo, compiled_at)"
        )
```

O índice é criado aqui, e não no schema, porque as colunas que ele referencia só existem depois do `ALTER TABLE` num banco antigo.

- [ ] **Step 5: Escrever `slug_livro`, `create_book` e `get_book`**

No topo de `bff/app/store.py`, junto dos outros imports:

```python
import unicodedata
```

E um bloco novo, depois de `list_sessions_since` (perto de `store.py:903`):

```python
# --- books (estante, fatia 1) ------------------------------------------------


def slug_livro(titulo: str) -> str:
    """Normaliza caixa, acento e espaço — e SÓ isso.

    Pontuação fica: descartá-la colapsaria "C", "C++" e "C#" numa obra só. O slug
    serve para não criar "Sapiens" e "sapiens " como duas obras, não para ser
    identidade semântica.
    """
    sem_acento = "".join(
        c
        for c in unicodedata.normalize("NFD", titulo)
        if unicodedata.category(c) != "Mn"
    )
    # Categoria "C*" cobre controle e formatação; vira espaço para o split colapsar.
    limpo = "".join(
        " " if unicodedata.category(c).startswith("C") else c for c in sem_acento
    )
    return " ".join(limpo.casefold().split())


def create_book(titulo: str) -> tuple[dict, bool]:
    """Cria ou reusa a obra de mesmo slug. Concorrência resolvida no banco."""
    slug = slug_livro(titulo)
    if not slug:
        raise ValueError("titulo_invalido")
    agora = time.time()
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        cur = con.execute(
            "INSERT INTO books (titulo, slug, status, ciclo, created, updated) "
            "VALUES (?, ?, 'lendo', 1, ?, ?) ON CONFLICT(slug) DO NOTHING",
            (" ".join(titulo.split()), slug, agora, agora),
        )
        criado = cur.rowcount == 1
        row = con.execute("SELECT * FROM books WHERE slug = ?", (slug,)).fetchone()
        con.commit()
        return dict(row), criado


def get_book(book_id: int) -> dict | None:
    with closing(_connect()) as con:
        row = con.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    return None if row is None else dict(row)
```

- [ ] **Step 6: Rodar os testes**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_books.py -v`
Expected: PASS, 6 testes.

- [ ] **Step 7: Rodar a suíte inteira**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest`
Expected: PASS. Nada existente pode quebrar — as colunas novas são nullable e a tabela é nova.

- [ ] **Step 8: Commit**

```bash
git add projects/escritorio/bff/app/store.py projects/escritorio/bff/tests/test_books.py
git commit -m "feat(escritorio): o livro vira linha no banco, com slug que nao mente"
```

---

### Task 3: `compiled_at` e as derivadas da estante

**Files:**
- Modify: `bff/app/store.py` (`finish_reading_compile` em `store.py:1254`; função nova `list_books`)
- Test: `bff/tests/test_books.py`

**Interfaces:**
- Consumes: `store.create_book`, `store.get_book` (Task 2)
- Produces: `store.list_books(status: str = "lendo") -> list[dict]`, cada item com as chaves `id, titulo, status, ciclo, pagina_atual, ultima_sessao, sessoes_n`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar em `bff/tests/test_books.py`:

```python
def _sessao_compilada(book_id, *, pagina_final, compiled_at, fim, key):
    """Grava direto na store o estado que /compile deixaria, para testar a derivada
    sem subir o pipeline inteiro de leitura.

    Não recebe o ciclo: quem o define é `create_reading_session`, copiando de
    `books.ciclo`. Passá-lo aqui esconderia justamente o que se quer testar.
    """
    sessao, _ = store.create_reading_session(
        key, "irrelevante", pagina_inicial=1, inicio=1.0, book_id=book_id
    )
    with store.closing(store._connect()) as con:
        con.execute(
            "UPDATE reading_sessions SET status='compiled', pagina_final=?, "
            "compiled_at=?, fim=? WHERE id=?",
            (pagina_final, compiled_at, fim, sessao["id"]),
        )
        con.commit()
    return sessao["id"]


def test_pagina_atual_e_da_sessao_compilada_mais_recente(db):
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], pagina_final=100, compiled_at=10.0, fim=10.0, key="a")
    _sessao_compilada(livro["id"], pagina_final=214, compiled_at=20.0, fim=20.0, key="b")

    estante = store.list_books("lendo")
    assert estante[0]["pagina_atual"] == 214
    assert estante[0]["sessoes_n"] == 2
    assert estante[0]["ultima_sessao"] == 20.0


def test_pagina_atual_ignora_o_relogio_do_celular(db):
    # A segunda sessão foi compilada depois (compiled_at maior) mas mandou um `fim`
    # atrasado. Ordenar por `fim` apontaria a página errada.
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], pagina_final=100, compiled_at=10.0, fim=999.0, key="a")
    _sessao_compilada(livro["id"], pagina_final=214, compiled_at=20.0, fim=5.0, key="b")

    assert store.list_books("lendo")[0]["pagina_atual"] == 214


def test_sessao_recente_sem_pagina_final_nao_apaga_o_progresso(db):
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], pagina_final=214, compiled_at=10.0, fim=10.0, key="a")
    _sessao_compilada(livro["id"], pagina_final=None, compiled_at=20.0, fim=20.0, key="b")

    assert store.list_books("lendo")[0]["pagina_atual"] == 214


def test_obra_sem_sessao_compilada(db):
    store.create_book("Recém-criada")
    linha = store.list_books("lendo")[0]
    assert linha["pagina_atual"] is None
    assert linha["ultima_sessao"] is None
    assert linha["sessoes_n"] == 0


def test_derivadas_ignoram_sessao_pendente(db):
    livro, _ = store.create_book("Sapiens")
    store.create_reading_session("p", "Sapiens", inicio=1.0, book_id=livro["id"])
    assert store.list_books("lendo")[0]["sessoes_n"] == 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_books.py -v -k "pagina_atual or derivadas or sem_sessao"`
Expected: FAIL — `create_reading_session() got an unexpected keyword argument 'book_id'`. É esperado: a Task 4 fecha esse argumento. Implemente o mínimo aqui (Step 3) e o restante na Task 4.

- [ ] **Step 3: Aceitar `book_id` em `create_reading_session` (mínimo)**

Em `bff/app/store.py:920`, trocar a assinatura e o INSERT. **Só a gravação** — a validação de status vem na Task 4:

```python
def create_reading_session(
    client_key: str,
    livro: str,
    pagina_inicial: int | None = None,
    inicio: float | None = None,
    book_id: int | None = None,
) -> tuple[dict, bool]:
    """Cria uma sessão retomável; retry da mesma client_key devolve a original."""
    agora = time.time()
    inicio_real = agora if inicio is None else float(inicio)
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE client_key = ?",
            (client_key,),
        ).fetchone()
        if row is not None:
            con.commit()
            return _reading_payload(con, row), False

        book_ciclo = None
        if book_id is not None:
            book = con.execute(
                "SELECT * FROM books WHERE id = ?", (book_id,)
            ).fetchone()
            if book is None:
                con.rollback()
                raise ValueError("book_nao_encontrado")
            # O ciclo é COPIADO, nunca inferido por tempo: `inicio` vem do cliente.
            book_ciclo = book["ciclo"]
            livro = book["titulo"]

        cur = con.execute(
            "INSERT INTO reading_sessions "
            "(client_key, livro, pagina_inicial, inicio, created, updated, "
            "book_id, book_ciclo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                client_key,
                livro,
                pagina_inicial,
                inicio_real,
                agora,
                agora,
                book_id,
                book_ciclo,
            ),
        )
        row = con.execute(
            "SELECT * FROM reading_sessions WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        con.commit()
        return _reading_payload(con, row), True
```

- [ ] **Step 4: Carimbar `compiled_at` no servidor**

Em `bff/app/store.py:1254`, dentro de `finish_reading_compile`, acrescentar `compiled_at` ao mesmo UPDATE que já existe:

```python
def finish_reading_compile(
    session_id: int,
    *,
    vault_path: str,
    compiled_session_id: int,
    pagina_final: int | None,
    fim: float,
    source_digest: str,
) -> dict:
    with closing(_connect()) as con:
        agora = time.time()
        con.execute("BEGIN IMMEDIATE")
        cur = con.execute(
            "UPDATE reading_sessions SET status = 'compiled', vault_path = ?, "
            "compiled_session_id = ?, pagina_final = COALESCE(?, pagina_final), "
            "fim = ?, source_digest = ?, last_error = NULL, updated = ?, "
            "compiled_at = ? "
            "WHERE id = ? AND status = 'compiling'",
            (
                vault_path,
                compiled_session_id,
                pagina_final,
                fim,
                source_digest,
                agora,
                agora,
                session_id,
            ),
        )
```

O resto da função fica igual. `compiled_at` é o relógio do **servidor**; `fim` continua sendo o do cliente, e serve só para duração e exibição.

- [ ] **Step 5: Escrever `list_books`**

Depois de `get_book` em `bff/app/store.py`:

```python
_ESTANTE_SQL = """
SELECT
  b.id, b.titulo, b.status, b.ciclo,
  (SELECT s.pagina_final FROM reading_sessions s
     WHERE s.book_id = b.id AND s.book_ciclo = b.ciclo
       AND s.status = 'compiled' AND s.pagina_final IS NOT NULL
     ORDER BY s.compiled_at DESC, s.id DESC LIMIT 1) AS pagina_atual,
  (SELECT MAX(s.compiled_at) FROM reading_sessions s
     WHERE s.book_id = b.id AND s.book_ciclo = b.ciclo
       AND s.status = 'compiled') AS ultima_sessao,
  (SELECT COUNT(*) FROM reading_sessions s
     WHERE s.book_id = b.id AND s.book_ciclo = b.ciclo
       AND s.status = 'compiled') AS sessoes_n
FROM books b
WHERE b.status = ?
ORDER BY ultima_sessao IS NULL, ultima_sessao DESC, b.id DESC
"""


def list_books(status: str = "lendo") -> list[dict]:
    """Estante: uma query só, com o progresso derivado das sessões do ciclo atual.

    `pagina_atual` ordena por `compiled_at` (relógio do servidor) e não por `fim`,
    que vem do cliente — celular atrasado apontaria a sessão errada como a última.
    `ultima_sessao IS NULL` primeiro no ORDER BY faz obra sem leitura cair no fim
    sem depender de NULLS LAST, que nem toda versão de SQLite tem.
    """
    with closing(_connect()) as con:
        rows = con.execute(_ESTANTE_SQL, (status,)).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 6: Rodar os testes**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_books.py -v`
Expected: PASS, 11 testes.

- [ ] **Step 7: Rodar a suíte inteira**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest`
Expected: PASS. `create_reading_session` ganhou um parâmetro com default; nenhum chamador existente muda.

- [ ] **Step 8: Commit**

```bash
git add projects/escritorio/bff/app/store.py projects/escritorio/bff/tests/test_books.py
git commit -m "feat(escritorio): a estante sabe a pagina, e nao pergunta ao celular que horas sao"
```

---

### Task 4: Ciclo de vida da obra na store, e a sessão que sabe de qual obra é

Corte por **camada**: esta task fecha o comportamento na `store`, testado direto contra ela. A Task 5 põe HTTP em cima. As duas terminam verdes sozinhas — a versão anterior deste plano fatiava por assunto e deixava a Task 4 vermelha até a 5 existir.

**Files:**
- Modify: `bff/app/store.py` (`create_reading_session` em `store.py:920`; funções novas depois de `list_books`)
- Test: `bff/tests/test_books.py`

**Interfaces:**
- Consumes: `store.create_book`, `store.list_books` (Tasks 2 e 3)
- Produces:
  - `store.BookIndisponivel` (exceção)
  - `store.terminar_book(book_id) -> tuple[str, dict | None]`, estado em `{"missing", "sessao_aberta", "ja_terminado", "terminado"}`
  - `store.reabrir_book(book_id) -> tuple[str, dict | None]`, estado em `{"missing", "ja_lendo", "reaberto"}`
  - `create_reading_session` recusando obra que não está em `lendo`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar em `bff/tests/test_books.py`:

```python
def test_terminar_e_reabrir_abrem_ciclo_novo(db):
    livro, _ = store.create_book("Sapiens")
    _sessao_compilada(livro["id"], pagina_final=300, compiled_at=10.0, fim=10.0, key="a")

    estado, obra = store.terminar_book(livro["id"])
    assert estado == "terminado" and obra["status"] == "terminado"
    assert store.list_books("lendo") == []
    assert store.list_books("terminado")[0]["id"] == livro["id"]

    estado, obra = store.reabrir_book(livro["id"])
    assert estado == "reaberto" and obra["ciclo"] == 2

    # A releitura recomeça: a página do ciclo 1 não vaza para o ciclo 2.
    assert store.list_books("lendo")[0]["pagina_atual"] is None
    _sessao_compilada(livro["id"], pagina_final=120, compiled_at=30.0, fim=30.0, key="b")
    assert store.list_books("lendo")[0]["pagina_atual"] == 120


def test_terminar_duas_vezes(db):
    livro, _ = store.create_book("Sapiens")
    assert store.terminar_book(livro["id"])[0] == "terminado"
    assert store.terminar_book(livro["id"])[0] == "ja_terminado"


def test_terminar_com_sessao_aberta_e_recusado(db):
    livro, _ = store.create_book("Sapiens")
    sessao, _ = store.create_reading_session(
        "aberta", "x", inicio=1.0, book_id=livro["id"]
    )
    estado, detalhe = store.terminar_book(livro["id"])
    assert estado == "sessao_aberta"
    assert detalhe["sessions"] == [sessao["id"]]
    assert store.get_book(livro["id"])["status"] == "lendo"


def test_terminar_obra_sem_sessao_funciona(db):
    # É assim que se tira da estante uma obra criada por engano.
    livro, _ = store.create_book("Criada sem querer")
    assert store.terminar_book(livro["id"])[0] == "terminado"


def test_reabrir_obra_que_ja_esta_lendo(db):
    livro, _ = store.create_book("Sapiens")
    assert store.reabrir_book(livro["id"])[0] == "ja_lendo"
    assert store.get_book(livro["id"])["ciclo"] == 1


def test_estados_de_obra_inexistente(db):
    assert store.terminar_book(9999)[0] == "missing"
    assert store.reabrir_book(9999)[0] == "missing"


def test_sessao_usa_o_titulo_canonico_e_o_ciclo_da_obra(db):
    livro, _ = store.create_book("Sapiens")
    sessao, _ = store.create_reading_session(
        "s1", "TÍTULO MENTIROSO", inicio=1.0, book_id=livro["id"]
    )
    assert sessao["livro"] == "Sapiens"
    assert sessao["book_id"] == livro["id"]
    assert sessao["book_ciclo"] == 1


def test_sessao_em_obra_terminada_e_recusada(db):
    livro, _ = store.create_book("Sapiens")
    store.terminar_book(livro["id"])
    with pytest.raises(store.BookIndisponivel):
        store.create_reading_session("s1", "x", inicio=1.0, book_id=livro["id"])
    assert store.get_reading_session(1) is None


def test_sessao_com_book_id_inexistente(db):
    with pytest.raises(ValueError, match="book_nao_encontrado"):
        store.create_reading_session("s1", "x", inicio=1.0, book_id=9999)
    assert store.get_reading_session(1) is None


def test_retry_da_mesma_client_key_nao_troca_a_obra(db):
    primeira, _ = store.create_book("Sapiens")
    segunda, _ = store.create_book("Antifrágil")
    store.create_reading_session("s1", "x", inicio=1.0, book_id=primeira["id"])

    sessao, criada = store.create_reading_session(
        "s1", "x", inicio=1.0, book_id=segunda["id"]
    )
    assert criada is False
    assert sessao["book_id"] == primeira["id"]


def test_sessao_sem_book_id_segue_o_caminho_antigo(db):
    sessao, _ = store.create_reading_session("s1", "Livro solto", inicio=1.0)
    assert sessao["livro"] == "Livro solto"
    assert sessao["book_id"] is None
    assert sessao["book_ciclo"] is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_books.py -v`
Expected: FAIL com `AttributeError: module 'app.store' has no attribute 'terminar_book'`

- [ ] **Step 3: Acrescentar a exceção e a validação de status**

Em `bff/app/store.py`, antes de `create_reading_session`:

```python
class BookIndisponivel(Exception):
    """A obra existe mas não aceita sessão nova (status != 'lendo').

    Separada de ValueError porque o HTTP é outro: 409 (conflito de estado) e não
    422 (referência inválida).
    """
```

E dentro de `create_reading_session`, no bloco `if book_id is not None:` criado na Task 3, entre a checagem de `book is None` e a cópia do ciclo:

```python
            if book["status"] != "lendo":
                con.rollback()
                raise BookIndisponivel("book_nao_aceita_sessao")
```

- [ ] **Step 4: Escrever `terminar_book` e `reabrir_book`**

Depois de `list_books` em `bff/app/store.py`:

```python
def terminar_book(book_id: int) -> tuple[str, dict | None]:
    """Fecha o ciclo. Sem efeito externo: é um UPDATE condicional e acabou.

    A tarefa de resumão no ClickUp é a fatia 2. Enquanto ela não existe, não há
    nada a reconciliar, então não há claim, lease nem status 'terminando'.
    """
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if row is None:
            con.rollback()
            return "missing", None
        abertas = con.execute(
            "SELECT id FROM reading_sessions WHERE book_id = ? AND book_ciclo = ? "
            "AND status IN ('pending', 'compiling') ORDER BY id",
            (book_id, row["ciclo"]),
        ).fetchall()
        if abertas:
            con.rollback()
            return "sessao_aberta", {"sessions": [r["id"] for r in abertas]}
        cur = con.execute(
            "UPDATE books SET status = 'terminado', updated = ? "
            "WHERE id = ? AND status = 'lendo'",
            (time.time(), book_id),
        )
        if cur.rowcount != 1:
            con.rollback()
            return "ja_terminado", None
        atualizado = con.execute(
            "SELECT * FROM books WHERE id = ?", (book_id,)
        ).fetchone()
        con.commit()
        return "terminado", dict(atualizado)


def reabrir_book(book_id: int) -> tuple[str, dict | None]:
    """Releitura abre um ciclo NOVO: a página recomeça e o histórico fica intacto."""
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT id FROM books WHERE id = ?", (book_id,)).fetchone()
        if row is None:
            con.rollback()
            return "missing", None
        cur = con.execute(
            "UPDATE books SET status = 'lendo', ciclo = ciclo + 1, updated = ? "
            "WHERE id = ? AND status = 'terminado'",
            (time.time(), book_id),
        )
        if cur.rowcount != 1:
            con.rollback()
            return "ja_lendo", None
        atualizado = con.execute(
            "SELECT * FROM books WHERE id = ?", (book_id,)
        ).fetchone()
        con.commit()
        return "reaberto", dict(atualizado)
```

- [ ] **Step 5: Rodar os testes**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_books.py -v`
Expected: PASS, 21 testes.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add projects/escritorio/bff/app/store.py projects/escritorio/bff/tests/test_books.py
git commit -m "feat(escritorio): terminar um livro e um UPDATE, nao um workflow"
```

---

### Task 5: Os quatro endpoints de obra

**Files:**
- Modify: `bff/app/main.py` (modelo da sessão perto de `main.py:365`; rotas novas antes de `@app.post("/reading/sessions")` em `main.py:1030`; endpoint da sessão em `main.py:1031`)
- Test: `bff/tests/test_estante_sessao.py`

**Interfaces:**
- Consumes: `store.create_book`, `store.list_books`, `store.terminar_book`, `store.reabrir_book`, `store.BookIndisponivel` (Tasks 2–4)
- Produces: `GET /reading/books?status=`, `POST /reading/books`, `POST /reading/books/{id}/terminar`, `POST /reading/books/{id}/reabrir`, e `book_id` no corpo de `POST /reading/sessions`

- [ ] **Step 1: Escrever os testes que falham**

Criar `bff/tests/test_estante_sessao.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app import store
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _nova_obra(client, titulo="Sapiens"):
    resp = client.post("/reading/books", json={"titulo": titulo})
    assert resp.status_code == 200
    return resp.json()["book"]


def test_criar_obra_e_idempotente_por_slug(client):
    primeira = client.post("/reading/books", json={"titulo": "Sapiens"})
    segunda = client.post("/reading/books", json={"titulo": "sapiens "})
    assert primeira.json()["created"] is True
    assert segunda.json()["created"] is False
    assert segunda.json()["book"]["id"] == primeira.json()["book"]["id"]


def test_criar_obra_com_titulo_vazio(client):
    resp = client.post("/reading/books", json={"titulo": "   "})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "titulo_invalido"


def test_listar_estante(client):
    _nova_obra(client, "Sapiens")
    resp = client.get("/reading/books")
    assert resp.status_code == 200
    linha = resp.json()["books"][0]
    assert linha["titulo"] == "Sapiens"
    assert linha["pagina_atual"] is None
    assert linha["sessoes_n"] == 0


def test_terminar_pela_api(client):
    obra = _nova_obra(client)
    assert client.post(f"/reading/books/{obra['id']}/terminar").status_code == 200
    assert client.get("/reading/books").json()["books"] == []
    assert len(client.get("/reading/books?status=terminado").json()["books"]) == 1

    repetido = client.post(f"/reading/books/{obra['id']}/terminar")
    assert repetido.status_code == 409
    assert repetido.json()["detail"] == "book_ja_terminado"


def test_reabrir_pela_api(client):
    obra = _nova_obra(client)
    client.post(f"/reading/books/{obra['id']}/terminar")
    resp = client.post(f"/reading/books/{obra['id']}/reabrir")
    assert resp.status_code == 200
    assert resp.json()["book"]["ciclo"] == 2

    repetido = client.post(f"/reading/books/{obra['id']}/reabrir")
    assert repetido.status_code == 409
    assert repetido.json()["detail"] == "book_ja_lendo"


def test_endpoints_de_obra_inexistente(client):
    assert client.post("/reading/books/9999/terminar").status_code == 404
    assert client.post("/reading/books/9999/reabrir").status_code == 404


def test_terminar_com_sessao_aberta_pela_api(client):
    obra = _nova_obra(client)
    client.post(
        "/reading/sessions",
        json={"client_key": "s1", "livro": "x", "inicio": 1.0, "book_id": obra["id"]},
    )
    resp = client.post(f"/reading/books/{obra['id']}/terminar")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "book_com_sessao_aberta"


def test_sessao_com_book_id_usa_o_titulo_canonico(client):
    obra = _nova_obra(client)
    resp = client.post(
        "/reading/sessions",
        json={
            "client_key": "s1",
            "livro": "TÍTULO MENTIROSO",
            "pagina_inicial": 10,
            "inicio": 1_000.0,
            "book_id": obra["id"],
        },
    )
    assert resp.status_code == 200
    sessao = resp.json()["session"]
    assert sessao["livro"] == "Sapiens"
    assert sessao["book_id"] == obra["id"]
    assert sessao["book_ciclo"] == 1


def test_sessao_com_book_id_inexistente_da_422(client):
    resp = client.post(
        "/reading/sessions",
        json={"client_key": "s1", "livro": "x", "inicio": 1.0, "book_id": 9999},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "book_nao_encontrado"


def test_sessao_em_obra_terminada_da_409(client):
    obra = _nova_obra(client)
    client.post(f"/reading/books/{obra['id']}/terminar")
    resp = client.post(
        "/reading/sessions",
        json={"client_key": "s1", "livro": "x", "inicio": 1.0, "book_id": obra["id"]},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "book_nao_aceita_sessao"


def test_sessao_sem_book_id_segue_o_caminho_antigo(client):
    resp = client.post(
        "/reading/sessions",
        json={"client_key": "s1", "livro": "Livro solto", "inicio": 1.0},
    )
    assert resp.status_code == 200
    assert resp.json()["session"]["book_id"] is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_estante_sessao.py -v`
Expected: FAIL com 404 em `/reading/books`.

- [ ] **Step 3: Escrever as quatro rotas**

Em `bff/app/main.py`, imediatamente antes de `@app.post("/reading/sessions")` (`main.py:1030`):

```python
class BookCreateIn(BaseModel):
    titulo: str


@app.get("/reading/books")
def listar_books(
    status: Literal["lendo", "terminado"] = "lendo",
    _auth: None = Depends(require_auth),
) -> dict:
    return {"books": store.list_books(status)}


@app.post("/reading/books")
def criar_book(
    body: BookCreateIn,
    _auth: None = Depends(require_auth),
) -> dict:
    try:
        book, created = store.create_book(body.titulo)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {"book": book, "created": created}


@app.post("/reading/books/{book_id}/terminar")
def terminar_book(
    book_id: int,
    _auth: None = Depends(require_auth),
) -> dict:
    estado, payload = store.terminar_book(book_id)
    if estado == "missing":
        raise HTTPException(404, "book_nao_encontrado")
    if estado == "sessao_aberta":
        raise HTTPException(409, "book_com_sessao_aberta")
    if estado == "ja_terminado":
        raise HTTPException(409, "book_ja_terminado")
    return {"book": payload}


@app.post("/reading/books/{book_id}/reabrir")
def reabrir_book(
    book_id: int,
    _auth: None = Depends(require_auth),
) -> dict:
    estado, payload = store.reabrir_book(book_id)
    if estado == "missing":
        raise HTTPException(404, "book_nao_encontrado")
    if estado == "ja_lendo":
        raise HTTPException(409, "book_ja_lendo")
    return {"book": payload}
```

Conferir que `Literal` já está importado de `typing` no topo de `main.py` (está — `main.py:220` usa `Literal`).

- [ ] **Step 4: Acrescentar `book_id` ao modelo e ao endpoint da sessão**

Em `bff/app/main.py`, na classe do corpo de `POST /reading/sessions` (perto de `main.py:365`), acrescentar o campo:

```python
    book_id: int | None = None
```

E no endpoint `create_reading_session` (`main.py:1031`), envolver a chamada à store:

```python
    try:
        session, created = store.create_reading_session(
            body.client_key,
            body.livro,
            body.pagina_inicial,
            body.inicio,
            book_id=body.book_id,
        )
    except store.BookIndisponivel:
        raise HTTPException(409, "book_nao_aceita_sessao") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
```

Manter o resto do corpo do endpoint como está.

- [ ] **Step 5: Rodar os testes**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_estante_sessao.py -v`
Expected: PASS, 11 testes.

- [ ] **Step 6: Rodar a suíte inteira**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add projects/escritorio/bff/app/main.py projects/escritorio/bff/tests/test_estante_sessao.py
git commit -m "feat(escritorio): a estante ganha porta de entrada"
```

---

### Task 6: Frontmatter — módulo puro

**Files:**
- Create: `bff/app/reading_frontmatter.py`
- Test: `bff/tests/test_reading_frontmatter.py`

**Interfaces:**
- Produces:
  - `reading_frontmatter.DRAFT_FMT: int` (valor `2`)
  - `reading_frontmatter.yaml_escalar(valor: str) -> str`
  - `reading_frontmatter.frontmatter(*, livro: str, pagina_inicial: int | None, pagina_final: int | None, inicio: float) -> str`

- [ ] **Step 1: Escrever os testes que falham**

Criar `bff/tests/test_reading_frontmatter.py`:

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_reading_frontmatter.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.reading_frontmatter'`

- [ ] **Step 3: Escrever o módulo**

Criar `bff/app/reading_frontmatter.py`:

```python
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
```

- [ ] **Step 4: Rodar os testes**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_reading_frontmatter.py -v`
Expected: PASS, 7 testes.

- [ ] **Step 5: Commit**

```bash
git add projects/escritorio/bff/app/reading_frontmatter.py projects/escritorio/bff/tests/test_reading_frontmatter.py
git commit -m "feat(escritorio): frontmatter que sobrevive a um titulo com dois-pontos"
```

---

### Task 7: Ligar o frontmatter em `/draft` e a guarda em `/compile`

**Files:**
- Modify: `bff/app/store.py` (`stage_reading_draft` em `store.py:1221`), `bff/app/main.py` (`/draft` em `main.py:1236-1257`, `/compile` em `main.py:1319`)
- Test: `bff/tests/test_estante_sessao.py`

**Interfaces:**
- Consumes: `reading_frontmatter.frontmatter`, `reading_frontmatter.DRAFT_FMT` (Task 6)
- Produces: `store.stage_reading_draft(session_id, draft_md, source_digest, draft_fmt)`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar em `bff/tests/test_estante_sessao.py`:

```python
from app import main


def _sessao_com_buffer(client, obra_id=None):
    corpo = {"client_key": "s1", "livro": "Sapiens", "pagina_inicial": 190, "inicio": 1.0}
    if obra_id is not None:
        corpo["book_id"] = obra_id
    sid = client.post("/reading/sessions", json=corpo).json()["session"]["id"]
    client.post(
        f"/reading/sessions/{sid}/buffer",
        json={"seq": 1, "hook": "comentario", "texto": "um comentário", "ts": 2.0},
    )
    return sid


def test_draft_prefixa_o_frontmatter_antes_do_staging(client, monkeypatch):
    obra = _nova_obra(client)
    sid = _sessao_com_buffer(client, obra["id"])

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        return "# Nota do Hermes"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)

    resp = client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    assert resp.status_code == 200
    draft = resp.json()["draft_md"]
    assert draft.startswith("---\n")
    assert 'livro: "Sapiens"' in draft
    assert "paginas: 190-214" in draft
    assert draft.endswith("# Nota do Hermes")
    # O que ficou staged é o documento COMPLETO: é ele que o Leo aprova.
    assert store.get_reading_session(sid)["draft_md"] == draft
    assert store.get_reading_session(sid)["draft_fmt"] == 2


def test_compile_recusa_draft_legado(client, monkeypatch):
    obra = _nova_obra(client)
    sid = _sessao_com_buffer(client, obra["id"])

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        return "# Nota do Hermes"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})

    # Simula o preview que já estava aberto no celular quando o deploy subiu.
    with store.closing(store._connect()) as con:
        con.execute("UPDATE reading_sessions SET draft_fmt = NULL WHERE id = ?", (sid,))
        con.commit()

    async def nunca(*_a, **_k):
        raise AssertionError("o vault não pode ser tocado com draft legado")

    monkeypatch.setattr(main.vault_client, "write_reading_note", nunca)

    resp = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 214, "fim": 100.0, "duracao_s": 60},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "reading_draft_desatualizado"
    assert store.get_reading_session(sid)["status"] == "pending"


def test_draft_legado_e_regenerado_e_nao_reusado(client, monkeypatch):
    obra = _nova_obra(client)
    sid = _sessao_com_buffer(client, obra["id"])
    chamadas = {"n": 0}

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        chamadas["n"] += 1
        return "# Nota do Hermes"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    assert chamadas["n"] == 1

    # Mesmo digest, mas formato antigo: tem que regenerar.
    with store.closing(store._connect()) as con:
        con.execute("UPDATE reading_sessions SET draft_fmt = NULL WHERE id = ?", (sid,))
        con.commit()
    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    assert chamadas["n"] == 2

    # Formato atual e mesmo digest: reusa, sem chamar o Hermes de novo.
    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    assert chamadas["n"] == 2
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_estante_sessao.py -v -k "frontmatter or legado"`
Expected: FAIL — o draft não começa com `---`.

- [ ] **Step 3: `stage_reading_draft` grava a versão do formato**

Em `bff/app/store.py:1221`:

```python
def stage_reading_draft(
    session_id: int, draft_md: str, source_digest: str, draft_fmt: int
) -> dict:
    """Guarda o preview e devolve a sessão a 'pending' (staged): fora do lock transitório
    de 'compiling', com o buffer congelado por draft_md não-nulo até aprovar/rejeitar."""
    with closing(_connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        cur = con.execute(
            "UPDATE reading_sessions SET draft_md = ?, source_digest = ?, "
            "draft_fmt = ?, status = 'pending', updated = ?, last_error = NULL "
            "WHERE id = ? AND status = 'compiling'",
            (draft_md, source_digest, draft_fmt, time.time(), session_id),
        )
```

O resto da função fica igual.

- [ ] **Step 4: Prefixar o frontmatter em `/draft`**

Em `bff/app/main.py`, acrescentar ao bloco de imports do pacote:

```python
from . import reading_frontmatter
```

E em `draft_reading_session` (`main.py:1236`), trocar o bloco de reuso/geração:

```python
    draft = session.get("draft_md")
    reusavel = (
        draft
        and session.get("source_digest") == source_digest
        and session.get("draft_fmt") == reading_frontmatter.DRAFT_FMT
    )
    if not reusavel:
        # Idempotência: um preview salvo do mesmo snapshot E do mesmo formato é
        # reusado sem chamar o Hermes. Formato antigo regenera e volta ao preview.
        try:
            nota = await hermes_client.compile_reading(
                session["livro"],
                session["buffer"],
                pagina_inicial=session.get("pagina_inicial"),
                pagina_final=body.pagina_final,
            )
        except Exception as exc:
            store.release_reading_compile(session_id, type(exc).__name__)
            store.log_event(
                "reading_compile_failed",
                ref=str(session_id),
                meta={"error": type(exc).__name__},
            )
            raise HTTPException(502, "reading_compile_indisponivel") from None
        draft = (
            reading_frontmatter.frontmatter(
                livro=session["livro"],
                pagina_inicial=session.get("pagina_inicial"),
                pagina_final=body.pagina_final,
                inicio=float(session["inicio"]),
            )
            + nota
        )

    session = store.stage_reading_draft(
        session_id, draft, source_digest, reading_frontmatter.DRAFT_FMT
    )
```

- [ ] **Step 5: Guardar `/compile`**

Em `bff/app/main.py:1319`, logo depois do bloco que checa `draft is None`:

```python
    if session.get("draft_fmt") != reading_frontmatter.DRAFT_FMT:
        # O preview já estava aberto no celular quando o deploy subiu: o digest
        # continua válido, então nada mais barraria a publicação sem frontmatter.
        store.release_reading_compile(session_id, "reading_draft_desatualizado")
        raise HTTPException(409, "reading_draft_desatualizado")
```

- [ ] **Step 6: Rodar os testes**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_estante_sessao.py -v`
Expected: PASS, 13 testes.

- [ ] **Step 7: Rodar a suíte inteira e consertar os testes de staging**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest`
Expected: FAIL em `test_reading_staging.py` — as asserções de igualdade exata do `draft_md` agora veem o frontmatter na frente.

Ajustar essas asserções para conferir o **sufixo** em vez da string inteira. Por exemplo, `test_draft_gera_preview_sem_tocar_vault_e_deixa_staged` (`test_reading_staging.py:63`):

```python
    assert body["draft_md"].endswith(f"# Preview\n\n> {quote}")
    assert body["draft_md"].startswith("---\n")
```

Aplicar a mesma troca em toda asserção de `draft_md == "..."` da suíte. Rodar de novo até o verde.

- [ ] **Step 8: Commit**

```bash
git add projects/escritorio/bff/app/ projects/escritorio/bff/tests/
git commit -m "feat(escritorio): o frontmatter entra antes do portao, nao depois"
```

---

### Task 8: Deck por obra — os três pontos de descarte

**Files:**
- Modify: `bff/app/anki.py`, `bff/app/store.py` (`_insert_anki_cards` em `store.py:2575`, `add_anki_cards` em `:2605`, `finish_anki_suggestion` em `:2661`), `bff/app/main.py` (`_suggest_anki_once` em `main.py:1016`, `/anki/sugerir` em `:2051`)
- Test: `bff/tests/test_estante_sessao.py`

**Interfaces:**
- Consumes: `store.get_book` (Task 2)
- Produces:
  - `anki.deck_para_livro(titulo: str) -> str`
  - `store._insert_anki_cards(con, cards, session_id, deck="")`
  - `store.add_anki_cards(cards, session_id=None, deck="")`
  - `store.finish_anki_suggestion(session_id, cards, deck="")`

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar em `bff/tests/test_estante_sessao.py`:

```python
from app import anki


def test_deck_para_livro():
    assert anki.deck_para_livro("Sapiens") == "Leitura::Sapiens"
    # `::` é o separador de subdeck do Anki: um título que o contenha criaria uma
    # árvore acidental.
    assert anki.deck_para_livro("A::B") == "Leitura::A-B"
    assert anki.deck_para_livro("  espaços  demais ") == "Leitura::espaços demais"
    assert anki.deck_para_livro("   ") == ""


def test_card_nasce_no_deck_da_obra(client, monkeypatch):
    obra = _nova_obra(client)
    sid = _sessao_com_buffer(client, obra["id"])

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        return "# Nota"

    async def suggest_anki(notas):
        # O modelo TENTA escolher o deck. O valor dele não pode valer.
        return [
            {
                "frente": "f",
                "meaning": "m",
                "example": "e",
                "hook": "h",
                "deck": "DeckDoModelo",
            }
        ]

    async def write_reading_note(*_a, **_k):
        return "Leituras/x.md"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    monkeypatch.setattr(main.hermes_client, "suggest_anki", suggest_anki)
    monkeypatch.setattr(main.vault_client, "write_reading_note", write_reading_note)

    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    resp = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 214, "fim": 100.0, "duracao_s": 60},
    )
    assert resp.status_code == 200
    cards = resp.json()["anki_cards"]
    assert cards[0]["deck"] == "Leitura::Sapiens"


def test_card_de_sessao_sem_obra_fica_sem_deck(client, monkeypatch):
    sid = _sessao_com_buffer(client)

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        return "# Nota"

    async def suggest_anki(notas):
        return [{"frente": "f", "meaning": "m", "example": "e", "hook": "h"}]

    async def write_reading_note(*_a, **_k):
        return "Leituras/x.md"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    monkeypatch.setattr(main.hermes_client, "suggest_anki", suggest_anki)
    monkeypatch.setattr(main.vault_client, "write_reading_note", write_reading_note)

    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    resp = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 214, "fim": 100.0, "duracao_s": 60},
    )
    assert resp.json()["anki_cards"][0]["deck"] == ""


def test_anki_sugerir_sem_session_id_nao_quebra(client, monkeypatch):
    async def suggest_anki(notas):
        return [{"frente": "f", "meaning": "m", "example": "e", "hook": "h"}]

    monkeypatch.setattr(main.hermes_client, "suggest_anki", suggest_anki)
    resp = client.post("/anki/sugerir", json={"notas": "algum texto"})
    assert resp.status_code == 200
    assert resp.json()["cards"][0]["deck"] == ""
```

E o teste do TSV:

```python
def test_tsv_carrega_o_deck_por_linha():
    linhas = anki.tsv(
        [
            {"frente": "a", "meaning": "b", "example": "c", "hook": "d",
             "deck": "Leitura::Sapiens"},
            {"frente": "e", "meaning": "f", "example": "g", "hook": "h", "deck": ""},
        ]
    )
    corpo = [l for l in linhas.splitlines() if not l.startswith("#")]
    assert corpo[0].split("\t")[4] == "Leitura::Sapiens"
    # Card antigo, sem obra: cai no deck-pai. O TSV NUNCA emite célula vazia —
    # é o que dispensa saber o que o Anki faria com ela.
    assert corpo[1].split("\t") == ["e", "f", "g", "h", "Leitura"]
    assert linhas.startswith("#separator:tab\n")


def test_tsv_nunca_emite_celula_de_deck_vazia():
    for card in ({"frente": "a"}, {"frente": "a", "deck": None}, {"frente": "a", "deck": "  "}):
        corpo = [l for l in anki.tsv([card]).splitlines() if not l.startswith("#")]
        assert corpo[0].split("\t")[4] == "Leitura"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_estante_sessao.py -v -k "deck or tsv or anki"`
Expected: FAIL com `AttributeError: module 'app.anki' has no attribute 'deck_para_livro'`

- [ ] **Step 3: `deck_para_livro` e a coluna no TSV**

Reescrever `bff/app/anki.py`:

```python
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
```

- [ ] **Step 4: Levar o deck até o INSERT**

Em `bff/app/store.py:2575`, `_insert_anki_cards`:

```python
def _insert_anki_cards(
    con: sqlite3.Connection,
    cards: list[dict],
    session_id: int | None,
    deck: str = "",
) -> list[dict]:
    """O deck vem por PARÂMETRO, nunca como chave do card.

    `_normalizar_anki_cards` descarta chaves desconhecidas de propósito: o dict vem
    da proposta do modelo, e o modelo não tem autoridade para escolher deck — se
    tivesse, uma injeção na leitura direcionaria cards para qualquer lugar.
    """
    criado = time.time()
    criados: list[dict] = []
    for card in cards:
        cur = con.execute(
            "INSERT INTO anki_cards "
            "(session_id, frente, meaning, example, hook, deck, criado) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                card["frente"],
                card["meaning"],
                card["example"],
                card["hook"],
                deck,
                criado,
            ),
        )
```

O resto da função fica igual.

Em `add_anki_cards` (`store.py:2605`) e `finish_anki_suggestion` (`store.py:2661`), acrescentar `deck: str = ""` à assinatura e repassar para `_insert_anki_cards`. O default existe porque `/anki/sugerir` chama as duas diretamente.

- [ ] **Step 5: Resolver o deck nos dois chamadores**

Em `bff/app/main.py:1016`, `_suggest_anki_once`:

```python
async def _suggest_anki_once(session_id: int, notas: str, deck: str = "") -> list[dict]:
    state = store.claim_anki_suggestion(session_id)
    if state == "done":
        return store.list_anki_cards_for_session(session_id)
    if state == "processing":
        raise RuntimeError("anki_suggestion_em_andamento")
    try:
        candidatos = await hermes_client.suggest_anki(notas)
        return store.finish_anki_suggestion(session_id, candidatos, deck)
    except Exception:
        store.release_anki_suggestion(session_id)
        raise
```

Acrescentar um resolvedor logo antes dele:

```python
def _deck_da_sessao(session: dict) -> str:
    """Deck determinado por código, a partir da obra da sessão de leitura."""
    book_id = session.get("book_id")
    if book_id is None:
        return ""
    book = store.get_book(int(book_id))
    return "" if book is None else anki.deck_para_livro(book["titulo"])
```

Nos dois pontos onde `_suggest_anki_once` é chamado no compile (`main.py:1283` e `main.py:1387`), passar `_deck_da_sessao(session)` como terceiro argumento.

Em `/anki/sugerir` (`main.py:2077`), resolver do mesmo jeito:

```python
    try:
        deck = ""
        if body.session_id is not None:
            sessao = store.get_reading_session(body.session_id)
            deck = _deck_da_sessao(sessao) if sessao else ""
        cards = (
            store.finish_anki_suggestion(body.session_id, candidatos, deck)
            if body.session_id is not None
            else store.add_anki_cards(candidatos)
        )
```

- [ ] **Step 6: Rodar os testes**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest tests/test_estante_sessao.py tests/test_anki.py -v`
Expected: PASS.

- [ ] **Step 7: Rodar a suíte inteira**

Run: `cd projects/escritorio/bff && .venv/Scripts/python -m pytest`
Expected: PASS. Se `test_anki.py` afirmar quatro colunas no TSV, atualizar para cinco.

- [ ] **Step 8: Commit**

```bash
git add projects/escritorio/bff/app/ projects/escritorio/bff/tests/
git commit -m "feat(escritorio): o deck existia no banco ha meses e nunca chegava no Anki"
```

---

### Task 9: App — cliente da API de obras

**Files:**
- Modify: `app/src/readingApi.ts`
- Test: `app/tests/shelfView.test.mjs` (criado na Task 10; aqui só o typecheck cobre)

**Interfaces:**
- Produces:
  - `type Book = { id: number; titulo: string; status: "lendo" | "terminado"; ciclo: number; pagina_atual: number | null; ultima_sessao: number | null; sessoes_n: number }`
  - `listBooks(status?)`, `createBook(titulo)`, `terminarBook(id)`, `reabrirBook(id)`
  - `book_id` em `createReadingSession`

- [ ] **Step 1: Acrescentar o tipo e as chamadas**

Em `app/src/readingApi.ts`, depois do tipo `ReadingSession`:

```typescript
export type Book = {
  id: number;
  titulo: string;
  status: "lendo" | "terminado";
  ciclo: number;
  // Derivadas do servidor: null = a obra ainda não tem sessão compilada no ciclo.
  pagina_atual: number | null;
  ultima_sessao: number | null;
  sessoes_n: number;
};
```

E no fim do arquivo:

```typescript
export async function listBooks(
  status: "lendo" | "terminado" = "lendo",
): Promise<{ books: Book[] }> {
  return request(`/reading/books?status=${status}`);
}

export async function createBook(
  titulo: string,
): Promise<{ book: Book; created: boolean }> {
  return request("/reading/books", {
    method: "POST",
    body: JSON.stringify({ titulo }),
  });
}

export async function terminarBook(bookId: number): Promise<{ book: Book }> {
  return request(`/reading/books/${bookId}/terminar`, { method: "POST" });
}

export async function reabrirBook(bookId: number): Promise<{ book: Book }> {
  return request(`/reading/books/${bookId}/reabrir`, { method: "POST" });
}
```

- [ ] **Step 2: Acrescentar `book_id` ao contrato da sessão**

No tipo `ReadingSession`, depois de `livro`:

```typescript
  book_id: number | null;
  book_ciclo: number | null;
```

E na assinatura de `createReadingSession`:

```typescript
export async function createReadingSession(body: {
  client_key: string;
  livro: string;
  pagina_inicial: number | null;
  inicio: number;
  book_id?: number | null;
}): Promise<{ session: ReadingSession; created: boolean }> {
```

- [ ] **Step 3: Guardar o `bookId` no rascunho local**

Em `app/src/readingDraft.ts:25`, acrescentar ao tipo `ReadingDraft`:

```typescript
  bookId: number | null;
```

E em `loadReadingDraft` (`readingDraft.ts:193`), normalizar rascunho antigo, que não tem o campo:

```typescript
    return {
      ...header,
      // Rascunho gravado antes da estante não tem bookId; `undefined` quebraria o
      // JSON do sync, então vira null explícito.
      bookId: header.bookId ?? null,
      activeSeconds: normalizeReadingActiveSeconds(
```

- [ ] **Step 4: Rodar o typecheck**

Run: `cd projects/escritorio/app && npm run typecheck`
Expected: FAIL — `Capture.tsx` cria um `ReadingDraft` sem `bookId` (`Capture.tsx:794`).

- [ ] **Step 5: Fechar o typecheck no ponto de criação**

Em `app/src/screens/Capture.tsx`, no objeto de `ensureSession` (`Capture.tsx:794`), acrescentar `bookId: selectedBookId,` — e declarar o estado junto dos outros, perto de `const [book, setBook] = ...`:

```typescript
  const [selectedBookId, setSelectedBookId] = useState<number | null>(null);
```

Em `resetSessionUi` (`Capture.tsx:836`), acrescentar `setSelectedBookId(null);`.

Onde a sessão é sincronizada com o servidor (`Capture.tsx:1289`, objeto com `livro: current.book`), acrescentar `book_id: current.bookId,`.

- [ ] **Step 6: Rodar o check completo**

Run: `cd projects/escritorio/app && npm run check`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add projects/escritorio/app/src/
git commit -m "feat(escritorio): o app aprende a falar de obra, nao so de titulo"
```

---

### Task 10: App — módulo puro da estante

**Files:**
- Create: `app/src/shelfView.ts`, `app/tests/shelfView.test.mjs`

**Interfaces:**
- Consumes: `Book` (Task 9) — estruturalmente, sem import de valor
- Produces: `montarEstante(books, agoraMs) -> LinhaEstante[]` com `LinhaEstante = { id, titulo, detalhe, paginaInicialSugerida }`

- [ ] **Step 1: Escrever o teste que falha**

Criar `app/tests/shelfView.test.mjs`:

```javascript
import assert from "node:assert/strict";
import test from "node:test";

import { montarEstante } from "../src/shelfView.ts";

const AGORA = 1_754_697_600_000; // ms
const DIA = 86_400_000;

function obra(over = {}) {
  return {
    id: 1,
    titulo: "Sapiens",
    status: "lendo",
    ciclo: 1,
    pagina_atual: 214,
    ultima_sessao: (AGORA - 3 * DIA) / 1000, // o servidor manda em segundos
    sessoes_n: 4,
    ...over,
  };
}

test("linha completa junta pagina e tempo", () => {
  const [linha] = montarEstante([obra()], AGORA);
  assert.equal(linha.titulo, "Sapiens");
  assert.equal(linha.detalhe, "pág. 214 · há 3 dias");
  assert.equal(linha.paginaInicialSugerida, "214");
});

test("obra sem sessao nao inventa pagina", () => {
  const [linha] = montarEstante(
    [obra({ pagina_atual: null, ultima_sessao: null, sessoes_n: 0 })],
    AGORA,
  );
  assert.equal(linha.detalhe, "ainda sem leitura");
  assert.equal(linha.paginaInicialSugerida, "");
});

test("obra lida sem pagina anotada mostra so o tempo", () => {
  const [linha] = montarEstante([obra({ pagina_atual: null })], AGORA);
  assert.equal(linha.detalhe, "há 3 dias");
  assert.equal(linha.paginaInicialSugerida, "");
});

test("tempo relativo cobre hoje, ontem, dias e semanas", () => {
  const casos = [
    [AGORA - 3600_000, "hoje"],
    [AGORA - 1.2 * DIA, "ontem"],
    [AGORA - 5 * DIA, "há 5 dias"],
    [AGORA - 14 * DIA, "há 2 semanas"],
    [AGORA - 70 * DIA, "há 10 semanas"],
  ];
  for (const [ms, esperado] of casos) {
    const [linha] = montarEstante([obra({ ultima_sessao: ms / 1000 })], AGORA);
    assert.ok(
      linha.detalhe.endsWith(esperado),
      `${linha.detalhe} deveria terminar com ${esperado}`,
    );
  }
});

test("leitura no futuro nao vira tempo negativo", () => {
  const [linha] = montarEstante([obra({ ultima_sessao: (AGORA + DIA) / 1000 })], AGORA);
  assert.ok(linha.detalhe.endsWith("hoje"));
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd projects/escritorio/app && node --test tests/shelfView.test.mjs`
Expected: FAIL — `Cannot find module '../src/shelfView.ts'`

- [ ] **Step 3: Escrever o módulo puro**

Criar `app/src/shelfView.ts`:

```typescript
// A estante é formatação — lógica pura, sem import de valor e sem relógio próprio.
// `agoraMs` entra por parâmetro: a tela é quem sabe que horas são, e o teste também.

// Estrutural de propósito: o `Book` de readingApi é atribuível a ela sem import.
export type ObraNaEstante = {
  id: number;
  titulo: string;
  pagina_atual: number | null;
  ultima_sessao: number | null; // segundos, como o servidor manda
};

export type LinhaEstante = {
  id: number;
  titulo: string;
  detalhe: string;
  // String porque o campo de página é um TextInput; "" quando não há o que sugerir.
  paginaInicialSugerida: string;
};

const DIA_MS = 86_400_000;

function tempoRelativo(ultimaSessaoS: number, agoraMs: number): string {
  // Leitura "no futuro" (relógio do celular adiantado quando gravou) vira hoje, e
  // não "há -1 dias".
  const dias = Math.max(0, Math.floor((agoraMs - ultimaSessaoS * 1000) / DIA_MS));
  if (dias === 0) return "hoje";
  if (dias === 1) return "ontem";
  if (dias < 7) return `há ${dias} dias`;
  const semanas = Math.floor(dias / 7);
  return `há ${semanas} ${semanas === 1 ? "semana" : "semanas"}`;
}

export function montarEstante(
  obras: ObraNaEstante[],
  agoraMs: number,
): LinhaEstante[] {
  return obras.map((obra) => {
    const partes: string[] = [];
    if (obra.pagina_atual !== null) partes.push(`pág. ${obra.pagina_atual}`);
    if (obra.ultima_sessao !== null) {
      partes.push(tempoRelativo(obra.ultima_sessao, agoraMs));
    }
    return {
      id: obra.id,
      titulo: obra.titulo,
      detalhe: partes.length ? partes.join(" · ") : "ainda sem leitura",
      paginaInicialSugerida:
        obra.pagina_atual === null ? "" : String(obra.pagina_atual),
    };
  });
}
```

- [ ] **Step 4: Rodar o teste**

Run: `cd projects/escritorio/app && node --test tests/shelfView.test.mjs`
Expected: PASS, 5 testes.

- [ ] **Step 5: Rodar o check completo**

Run: `cd projects/escritorio/app && npm run check`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add projects/escritorio/app/src/shelfView.ts projects/escritorio/app/tests/shelfView.test.mjs
git commit -m "feat(escritorio): a linha da estante e funcao pura, e o relogio entra por fora"
```

---

### Task 11: App — a estante na tela de Leitura

**Files:**
- Modify: `app/src/screens/Capture.tsx` (bloco de setup em `Capture.tsx:1527-1567`)

**Interfaces:**
- Consumes: `montarEstante` (Task 10); `listBooks`, `createBook`, `terminarBook`, `reabrirBook`, `Book` (Task 9)

- [ ] **Step 1: Carregar a estante**

Em `app/src/screens/Capture.tsx`, acrescentar aos imports que já existem no topo:

```typescript
import { Alert, ActivityIndicator } from "react-native";        // junte aos já importados
import {
  createBook,
  listBooks,
  reabrirBook,
  terminarBook,
  type Book,
} from "../readingApi";                                          // junte ao import existente
import { montarEstante, type LinhaEstante } from "../shelfView";
```

`readingErrorDetail` já vem de `readingApi` (é reexportado em `readingApi.ts:4`); `useCallback` e `useEffect` já estão importados de `react`.

E junto dos outros `useState` do modo leitura:

```typescript
  const [shelf, setShelf] = useState<Book[] | null>(null);
  const [finished, setFinished] = useState<Book[] | null>(null);
  const [showFinished, setShowFinished] = useState(false);
  const [shelfBusyId, setShelfBusyId] = useState<number | null>(null);
  const [newBookMode, setNewBookMode] = useState(false);

  const loadShelf = useCallback(async () => {
    try {
      const { books } = await listBooks("lendo");
      setShelf(books);
    } catch {
      // null = NÃO CARREGOU. A tela mostra o campo livre, e nunca uma estante
      // vazia que o Leo leria como "não tenho livro nenhum".
      setShelf(null);
    }
  }, []);

  useEffect(() => {
    if (mode === "leitura") void loadShelf();
  }, [mode, loadShelf]);
```

- [ ] **Step 2: Escolher uma obra**

```typescript
  function escolherObra(linha: LinhaEstante): void {
    setSelectedBookId(linha.id);
    setBook(linha.titulo);
    // Sugestão, não imposição: pode ter lido no papel desde a última sessão.
    setPageStart(linha.paginaInicialSugerida);
    setPageEnd("");
    setNewBookMode(false);
  }

  async function criarObra(): Promise<void> {
    const titulo = book.trim();
    if (!titulo) return;
    try {
      const { book: criada } = await createBook(titulo);
      setSelectedBookId(criada.id);
      setBook(criada.titulo);
      await loadShelf();
    } catch (error) {
      setSpeechError(readingErrorDetail(error) ?? "não deu para registrar a obra");
    }
  }
```

`criarObra` roda **antes** de `beginSession`/`startSession` quando `newBookMode` está ativo.

- [ ] **Step 3: Terminar e reabrir**

```typescript
  async function terminarObra(bookId: number, titulo: string): Promise<void> {
    setShelfBusyId(bookId);
    try {
      await terminarBook(bookId);
      await loadShelf();
    } catch (error) {
      const detalhe = readingErrorDetail(error);
      if (detalhe === "book_ja_terminado") {
        // Já terminada em outro lugar: recarregar é a resposta certa, não um erro.
        await loadShelf();
      } else if (detalhe === "book_com_sessao_aberta") {
        setSpeechError(`termine a sessão de leitura de ${titulo} antes`);
      } else {
        setSpeechError("não deu para terminar a obra");
      }
    } finally {
      setShelfBusyId(null);
    }
  }

  async function reabrirObra(bookId: number): Promise<void> {
    setShelfBusyId(bookId);
    try {
      await reabrirBook(bookId);
      await loadShelf();
      setFinished((await listBooks("terminado")).books);
    } catch {
      setSpeechError("não deu para reabrir a obra");
    } finally {
      setShelfBusyId(null);
    }
  }
```

- [ ] **Step 4: Tratar a obra terminada no início da sessão**

Onde a sessão é criada no servidor (o `createReadingSession` do sync), tratar o 409:

```typescript
      if (readingErrorDetail(error) === "book_nao_aceita_sessao") {
        setSpeechError("essa obra foi terminada — reabra antes de ler");
        setSelectedBookId(null);
        await loadShelf();
        return;
      }
```

- [ ] **Step 5: Trocar o bloco de setup**

Substituir o conteúdo do `<Card style={styles.setupCard}>` (`Capture.tsx:1527`). Manter os dois campos de página e os dois botões como estão; trocar só o `Field` do livro:

```tsx
          <Card style={styles.setupCard}>
            <Text style={styles.setupLabel}>O QUE VOCÊ ESTÁ LENDO?</Text>

            {shelf && !newBookMode ? (
              <>
                {montarEstante(shelf, Date.now()).map((linha) => (
                  <Pressable
                    key={linha.id}
                    style={[
                      styles.shelfRow,
                      selectedBookId === linha.id && styles.shelfRowActive,
                    ]}
                    onPress={() => escolherObra(linha)}
                    disabled={shelfBusyId !== null}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={styles.shelfTitle} numberOfLines={1}>
                        {linha.titulo}
                      </Text>
                      <Text style={styles.shelfDetail}>{linha.detalhe}</Text>
                    </View>
                    <Pressable
                      onPress={() => terminarObra(linha.id, linha.titulo)}
                      hitSlop={10}
                      disabled={shelfBusyId !== null}
                    >
                      {shelfBusyId === linha.id ? (
                        <ActivityIndicator size="small" color={colors.primary} />
                      ) : (
                        <Feather name="check" size={17} color={colors.muted} />
                      )}
                    </Pressable>
                  </Pressable>
                ))}
                <Pressable
                  onPress={() => {
                    setNewBookMode(true);
                    setSelectedBookId(null);
                    setBook("");
                    setPageStart("");
                  }}
                  style={styles.shelfAdd}
                >
                  <Feather name="plus" size={14} color={colors.primary} />
                  <Text style={styles.shelfAddText}>novo livro</Text>
                </Pressable>
              </>
            ) : (
              <Field
                value={book}
                onChangeText={(value) => updateReadingField(setBook, value)}
                placeholder="Livro, artigo ou capítulo"
                editable={readingDraftReady}
              />
            )}
```

O `✓` de terminar fica dentro da linha, com `hitSlop` para não competir com o toque de escolher. `shelf === null` (não carregou) cai no campo livre de sempre — degradação, não tela vazia.

- [ ] **Step 6: Confirmação antes de terminar**

Usar o `Alert` do React Native no `onPress` do `✓`, sem chamar `terminarObra` direto:

```typescript
  function confirmarTerminar(bookId: number, titulo: string): void {
    Alert.alert("Terminar obra", `Terminar ${titulo}?`, [
      { text: "cancelar", style: "cancel" },
      { text: "terminar", onPress: () => void terminarObra(bookId, titulo) },
    ]);
  }
```

Trocar o `onPress` do `✓` para `confirmarTerminar(linha.id, linha.titulo)`. Conferir que `Alert` está importado de `react-native`.

- [ ] **Step 7: Lista de obras terminadas**

Abaixo do bloco da estante, dentro do mesmo `Card`:

```tsx
            <Pressable
              onPress={async () => {
                const proximo = !showFinished;
                setShowFinished(proximo);
                if (proximo) {
                  try {
                    setFinished((await listBooks("terminado")).books);
                  } catch {
                    setFinished(null);
                  }
                }
              }}
            >
              <Text style={styles.shelfLink}>
                {showFinished ? "esconder terminadas" : "ver obras terminadas"}
              </Text>
            </Pressable>
            {showFinished && finished
              ? finished.map((obra) => (
                  <View key={obra.id} style={styles.shelfRow}>
                    <Text style={styles.shelfTitle} numberOfLines={1}>
                      {obra.titulo}
                    </Text>
                    <Pressable
                      onPress={() => void reabrirObra(obra.id)}
                      disabled={shelfBusyId !== null}
                    >
                      <Text style={styles.shelfLink}>reabrir</Text>
                    </Pressable>
                  </View>
                ))
              : null}
```

- [ ] **Step 8: Acrescentar os estilos**

No `StyleSheet.create` do arquivo, junto dos estilos de leitura:

```typescript
  shelfRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  shelfRowActive: { backgroundColor: colors.surfaceAlt },
  shelfTitle: { color: colors.text, fontSize: 15, flex: 1 },
  shelfDetail: { color: colors.muted, fontSize: 12, marginTop: 2 },
  shelfAdd: { flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: 12 },
  shelfAddText: { color: colors.primary, fontSize: 13 },
  shelfLink: { color: colors.primary, fontSize: 12, paddingVertical: 8 },
```

Conferir contra `app/src/theme.ts` que `colors.surfaceAlt`, `colors.border` e `colors.muted` existem; se algum não existir, usar o equivalente que os estilos vizinhos de `Capture.tsx` já usam.

- [ ] **Step 9: Rodar o check completo**

Run: `cd projects/escritorio/app && npm run check`
Expected: PASS.

- [ ] **Step 10: Rodar o app e conferir na mão**

Run: `cd projects/escritorio/app && npx expo start`

Roteiro, com o BFF de pé:
1. Abrir Captura → Leitura. Estante vazia, só "novo livro".
2. "novo livro" → digitar "Sapiens" → começar leitura → ditar um comentário → compilar → aprovar.
3. Voltar à Leitura: "Sapiens" aparece com a página e "hoje".
4. Tocar em "Sapiens": o campo de página inicial já vem preenchido.
5. `✓` → confirmar → some da estante.
6. "ver obras terminadas" → "Sapiens" está lá → "reabrir" → volta, e a página some (ciclo novo).
7. Conferir no Obsidian que a nota tem o frontmatter e que o path continua neutro.

- [ ] **Step 11: Commit**

```bash
git add projects/escritorio/app/src/screens/Capture.tsx
git commit -m "feat(escritorio): a leitura para de perguntar o que voce ja disse tres vezes"
```

---

## Self-Review

**Cobertura da spec (fatia 1):**

| Seção da spec | Task |
|---|---|
| Tabela `books`, slug, migração | 2 |
| Ciclo copiado (D-L) | 3 (cópia), 4 (incremento no `reabrir`) |
| Derivadas, `compiled_at` (D-P) | 3 |
| Sessão com `book_id`, validação de status (D-M) | 3 (cópia), 4 (validação) |
| terminar/reabrir sem efeito externo (D-Q) | 4 (store), 5 (rotas) |
| Frontmatter (D-H), YAML seguro | 6, 7 |
| `draft_fmt` nos dois endpoints (D-O) | 7 |
| Deck nos três pontos (D-F), TSV | 8 |
| Tela da estante | 9, 10, 11 |

**Toda task termina verde.** A primeira versão deste plano fatiava as Tasks 4 e 5 por assunto (modelo de sessão / endpoints de obra) e deixava `test_estante_sessao.py` vermelho entre as duas. O corte agora é por **camada** — Task 4 fecha a `store` e testa direto contra ela; Task 5 põe HTTP em cima. Mesma granularidade de revisão, sem estado intermediário quebrado.

**Não coberto nesta fatia, de propósito:** tarefa de resumão no ClickUp (fatia 2), recap do Hermes (fatia 3). Ambas estão especificadas no fim de `ESTANTE-SPEC.md` com as pendências que as três rodadas de revisão levantaram.
