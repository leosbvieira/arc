---
artifact: skill-spec
capability: escritorio
skill: estante (lane "Leitura")
status: proposed
date: 2026-08-09
revision: 2 (pós-revisão hostil GPT-5.6 Sol, 2026-08-09)
source_refs:
  - READING-STAGING-SPEC.md
  - AETERNUM-SPEC.md
  - CAPTURE-GRAMMAR-SPEC.md
  - "brainstorm 2026-08-09 (Leo + Claude): livro como entidade"
  - "revisão hostil 2026-08-09 (GPT-5.6 Sol, high): 15 achados, veredito 'revisar antes de implementar'"
engine: Hermes (profile "Leitura") — só para o recap, best-effort
implements: "livro como entidade: retomar de onde parou, agrupar por obra, deck por obra"
---

# SKILL SPEC — estante (lane "Leitura")

Promove **livro** de string redigitada a **entidade**. Hoje a lane Leitura pergunta "o que
você vai ler?" num campo de texto livre (`Capture.tsx:1529`) e a página inicial você digita
de memória. Nada se acumula por obra: nem o ponto onde parou, nem os comentários, nem os
cards do Anki.

O dado para responder "em que página eu estava" **já está gravado**. `reading_sessions`
guarda `livro`, `pagina_inicial`, `pagina_final` e a linha **sobrevive ao compile**
(vira `status='compiled'`, `store.py:1266`). Sessões compiladas até são lidas de volta —
no reconcile e nos retries (`main.py:1188`). O que nunca existiu é leitura desse dado
**como progresso por obra**.

**Simetria que motivou a spec:** a nota da sessão já tem staging e vai pro vault; os cards
já têm staging e vão pro Anki. A **obra** — o eixo em torno do qual as duas coisas fazem
sentido — não existia em lugar nenhum.

## Decisões (brainstorm 2026-08-09)

- **D-A — tabela `books` mínima, progresso derivado.** A estante nasce de uma tabela, mas
  a tabela guarda **só o que sessão nenhuma consegue carregar**: título, slug, status, ciclo.
  Página atual e data da última leitura são **derivadas** das sessões compiladas — se virassem
  colunas, divergiriam do histórico no primeiro crash. Sem capa, sem ISBN, sem total de
  páginas, sem nota. (Estante 100% derivada foi descartada: "terminei o livro" é estado que
  nenhuma sessão carrega, e o deck do Anki precisa de identidade estável.)
- **D-B — recap gerado no fim da sessão anterior, não no começo da próxima.** O Hermes já é
  chamado no compile. O recap nasce ali e fica **guardado na sessão**; a próxima sessão só
  **lê**. Custo zero de espera na hora de começar a ler.
- **D-C — tudo é obra.** Artigo e capítulo avulso entram na mesma tabela. Um artigo é só uma
  obra que termina em uma sessão. Um caminho só na tela, sem ramo especial.
- **D-D — começar do zero.** O histórico fica com `book_id NULL`. A estante nasce vazia e
  cresce com as próximas sessões. (Backfill por slug foi descartado: agruparia errado os
  títulos digitados de forma diferente.)
- **D-E — lei 7 preservada, agrupamento por dentro.** Os paths do vault seguem neutros
  (`Leituras/2026-08-09 - leitura-r42-<hash>.md`). O título da obra entra no **frontmatter**
  da nota, não no caminho.
- **D-F — deck `Leitura::<Título>`.** Subdeck te deixa escolher na hora de revisar: `Leitura`
  puxa de todas as obras, `Leitura::Sapiens` puxa de uma. O TSV sai pro Anki local, não pro
  git — a lei 7 protege o repositório, e o Anki não é o repositório.
- **D-G — terminar o livro vira tarefa, não tela.** Marcar `terminado` cria uma tarefa no
  ClickUp (Staging, como toda tarefa, lei 3) com um template de resumão já apontando pras
  notas daquela obra.

## Decisões acrescentadas na revisão 2

A revisão hostil derrubou três pontos da revisão 1. Ficam registrados os erros, não só as
correções — o motivo de cada um é o que impede a reincidência.

- **D-H — o frontmatter entra ANTES do staging.** A revisão 1 mandava colar o frontmatter
  na hora de gravar no vault. Isso **furava o portão humano**: `main.py:1319` lê `draft_md`
  e `main.py:1332` grava **exatamente esse texto**; o `source_digest` (`main.py:1327`) existe
  para garantir que o publicado é o aprovado. Colar qualquer coisa depois da aprovação quebra
  a lei de fidelidade no ponto onde ela é mais explícita. Agora o frontmatter é composto em
  `/draft` (`main.py:1255`), **antes** de `stage_reading_draft` — você aprova o documento
  inteiro, e o compile segue gravando byte-a-byte.
- **D-I — o recap não vê citações.** A revisão 1 mandava gerar o recap "a partir da nota
  recém-gerada". Mas a nota tem as citações coladas por código (`hermes_client.py:346`), e o
  payload do modelo as exclui de propósito (`hermes_client.py:310-317`). Uma citação com texto
  instrucional passaria a entrar no prompt. O recap agora sai do **mesmo payload estruturado
  sem citações** que o `READING_FRAME` usa, com o mesmo enquadramento de dado não confiável.
- **D-J — página atual é a da sessão mais recente, não o máximo.** `MAX(pagina_final)` mente
  em releitura: sessão antiga terminou na 300, releitura está na 120, a estante ofereceria 300.
  Agora é a `pagina_final` da sessão compilada mais recente **do ciclo atual** — e o ciclo
  (D-K) é o que torna releitura bem definida.
- **D-K — ciclo de leitura.** `reabrir` não volta ao estado anterior: abre um **ciclo novo**.
  Isso resolve dois furos de uma vez: a página volta a contar do zero na releitura, e o
  segundo resumão cobre as sessões do segundo ciclo em vez de reapontar para a tarefa velha.

## Bug encontrado: `deck` é descartado em três pontos

Não é feature nova, é conserto — e maior do que a revisão 1 estimou. A coluna
`anki_cards.deck` **existe** (`store.py:201`, default `''`) e o PATCH escreve nela
(`main.py:828`). Mas o valor nunca chega lá, porque cai três vezes:

1. `store.py:2563` — `_normalizar_anki_cards` monta `{"frente": frente}` e depois só itera
   `("meaning", "example", "hook")`. Qualquer outra chave é descartada.
2. `store.py:2584` — `_insert_anki_cards` faz
   `INSERT INTO anki_cards (session_id, frente, meaning, example, hook, criado)`. `deck` não
   está no INSERT.
3. `anki.py:10` — o TSV serializa exatamente quatro campos, e `deck` não é um deles.

**O descarte em (1) é correto e fica.** `_normalizar_anki_cards` recebe a proposta **do
modelo**, e o modelo não tem autoridade para escolher deck. Se o deck viajasse como campo do
dict, uma injeção na leitura poderia direcionar cards para qualquer deck. O deck é
**determinado por código** a partir do `book_id` da sessão, então viaja como **parâmetro de
função**, nunca como chave do card:

```
_suggest_anki_once(session_id, notas, deck)
  → finish_anki_suggestion(session_id, cards, deck)
    → _insert_anki_cards(con, cards, session_id, deck)
```

`add_anki_cards(cards, session_id=None, deck="")` ganha o mesmo parâmetro. O caminho de
retry (`main.py:1188`) devolve cards já inseridos via `list_anki_cards_for_session` e não
reinsere — não precisa de deck.

## Modelo de dados

```sql
CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  titulo TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'lendo',   -- 'lendo' | 'terminando' | 'terminado'
  ciclo INTEGER NOT NULL DEFAULT 1,
  ciclo_inicio REAL NOT NULL,
  resumo_task_id TEXT,
  resumo_ciclo INTEGER,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reading_sessions_book
  ON reading_sessions(book_id, inicio);
```

`reading_sessions` ganha `book_id INTEGER` (nullable, D-D) e `recap TEXT` (nullable, D-B).

### Slug: dedup, não identidade

`slug` normaliza **só** caixa, acentos e espaços em excesso. **Pontuação é preservada** — a
revisão hostil apontou com razão que descartar pontuação colapsaria "C", "C++" e "C#" numa
obra só. Slug que resulte vazio (título só de espaço/controle) é **rejeitado** com 422
`titulo_invalido`; não existe obra de slug vazio.

O slug serve para você não criar "Sapiens" e "sapiens " como duas obras. O `titulo` guarda o
que você digitou, e é ele que vai para o deck e para o frontmatter.

### O ciclo torna releitura bem definida

`ciclo_inicio` é gravado na criação e reescrito a cada `reabrir`. As sessões do ciclo atual
são `reading_sessions WHERE book_id = ? AND inicio >= ciclo_inicio` — sem coluna nova em
`reading_sessions`.

### Derivadas (uma fonte de verdade só)

Calculadas sobre as sessões `status='compiled'` **do ciclo atual**:

- `pagina_atual` = `pagina_final` da sessão mais recente por `fim DESC, id DESC` **que tenha
  `pagina_final NOT NULL`**. Sessão recente sem página final não apaga o progresso: a query
  cai na anterior que tenha. Obra sem nenhuma sessão com página → `null`, e a tela mostra o
  campo vazio em vez de "pág. null".
- `ultima_sessao` = `MAX(fim)`.
- `recap` = o `recap` da sessão compilada mais recente do ciclo.

## Uma fonte de verdade para o título da sessão

`POST /reading/sessions` aceita `book_id` opcional. Com `book_id`:

- o servidor **busca a obra e copia o `titulo` canônico** para `reading_sessions.livro`;
- qualquer `livro` que venha no corpo é **ignorado** — o servidor manda;
- `book_id` inexistente → 422 `book_nao_encontrado`, sem criar sessão.

Sem `book_id`, o comportamento é o de hoje (`livro` como texto solto). O caminho antigo não
quebra.

**Por que copiar em vez de referenciar:** `reading_sessions.livro` entra no `source_digest`
(`main.py:1313`). Copiando na criação, renomear a obra depois **não reescreve o histórico**
nem invalida o digest de sessões já compiladas.

**Por que `book_id` NÃO entra no `source_digest`:** a única coisa que a obra determina é o
título — e o título já está no digest, copiado e imutável. Deck e frontmatter derivam desse
mesmo título. Acrescentar `book_id` ao digest invalidaria drafts antigos sem cobrir nada
novo. `book_id` **entra** no `ReadingSession` devolvido pela API (o app precisa dele para a
tela) e no `ReadingSnapshot` só como campo informativo, não comparado.

## Endpoints

- `GET /reading/books?status=lendo` → `[{id, titulo, status, ciclo, pagina_atual,
  ultima_sessao, sessoes_n, recap}]`. Uma query com agregação, sem N+1.
- `POST /reading/books` `{titulo}` → cria ou **reusa** a obra de mesmo slug. Devolve
  `{book, created}` — mesmo contrato de `createReadingSession` (`readingApi.ts:99`).
  Título de slug vazio → 422 `titulo_invalido`.
- `POST /reading/books/{id}/terminar` → ver abaixo.
- `POST /reading/books/{id}/reabrir` → `status='lendo'`, `ciclo += 1`, `ciclo_inicio = agora`.
  Não mexe na tarefa do ciclo anterior. Obra em `terminando` → 409 `book_terminando`.

### `terminar`: claim atômico, ClickUp primeiro, transação local depois

O padrão é o de `claim_reading_compile` (`store.py:1178`), que já existe e já tem recuperação
de lease velho no `init_db` (`store.py:263-270`, `CLAIM_STALE_SECONDS`).

1. **Claim:** `UPDATE books SET status='terminando', updated=? WHERE id=? AND status='lendo'`.
   `rowcount = 0` → 409 (`book_terminando` ou `book_ja_terminado`, conforme o status atual).
   Dois toques simultâneos: só um passa.
2. **Reconciliar antes de criar:** `find_task_by_marker` com o marker do ciclo, exatamente
   como a captura faz (`capture_pipeline.py:175-182`). Cobre o crash entre criar no ClickUp e
   persistir o id.
3. **Criar** a tarefa em Staging se o marker não existir.
4. **Persistir** `status='terminado'`, `resumo_task_id`, `resumo_ciclo = ciclo` numa **única
   transação local**.
5. **Falha em (2) ou (3):** `release` → `status='lendo'`, e 502 `clickup_indisponivel`. A obra
   **nunca** sai da estante sem tarefa criada.

**Idempotência por ciclo:** se `resumo_ciclo == ciclo`, `terminar` devolve a tarefa existente
com `created:false` sem tocar no ClickUp. Terminar → reabrir → terminar cria uma tarefa nova,
do ciclo 2, cobrindo as sessões do ciclo 2. Foi por isso que o ciclo entrou (D-K): sem ele o
segundo resumão apontaria para as notas do primeiro.

**Marker:** `[book-summary:{book_id}:{ciclo}]`, no corpo da descrição. A revisão 1 prometia
reconciliação por marker e não punha marker nenhum no template.

## Tela

A `Card` de setup da Leitura (`Capture.tsx:1527`) troca o campo livre pela estante:

```
O QUE VOCÊ ESTÁ LENDO?

  Sapiens                        pág. 214 · há 3 dias      ✓
  Antifrágil                     pág. 88  · há 2 semanas   ✓
  + novo livro
                                       ver obras terminadas
```

- **Tocar na linha** abre o setup com `livro` e `pagina_inicial` preenchidos. `pagina_inicial`
  é o `pagina_atual` derivado, **editável** (você pode ter lido no papel desde então).
- **`✓`** marca terminado. Confirmação antes: *"Terminar Sapiens? Cria a tarefa de resumão em
  Staging."* Durante a chamada a linha fica desabilitada com spinner. Erro → mensagem inline e
  a linha volta ao normal (o servidor já liberou o claim). 409 de obra já terminada →
  recarrega a estante em vez de mostrar erro.
- **`+ novo livro`** abre o campo de texto de hoje, que agora chama `POST /reading/books`
  antes de começar a sessão.
- **`ver obras terminadas`** abre a lista de `status=terminado`, cada uma com **reabrir** e o
  link da tarefa de resumão. É onde a obra volta pra estante.

Quando há `recap`, ele aparece acima do botão, em duas ou três linhas. É texto guardado, não
chamada de modelo — aparece instantâneo.

Estante vazia (o estado do primeiro dia, por D-D) mostra só `+ novo livro`. As sessões
pendentes de "RETOMAR SESSÃO" (`Capture.tsx:1509`) continuam acima e inalteradas — são outra
coisa: sessão inacabada, não obra em andamento.

## O frontmatter (dentro do portão)

Em `/draft`, entre `compile_reading` (`main.py:1240`) e `stage_reading_draft`
(`main.py:1255`), o código prepende:

```yaml
---
livro: "Sapiens"
paginas: 190-214
data: 2026-08-09
---
```

Escrito **por código**, nunca pelo modelo: `livro` vem da tabela, `paginas` da sessão, `data`
do `inicio`. O que você aprova no preview já é o documento completo, e o compile continua
gravando `draft_md` byte-a-byte.

**Serialização segura, sem dependência nova.** O BFF não tem PyYAML (`requirements.txt`) e
não vale acrescentar por causa de três linhas. Só `livro` é texto livre; `paginas` e `data`
são gerados por código. Então `livro` sai **sempre como escalar entre aspas duplas**, com
`\` → `\\`, `"` → `\"`, e quebras de linha e caracteres de controle colapsados em espaço.
Aspas sempre presentes resolvem de uma vez `:`, `#`, `---`, e títulos como `yes` ou `123` que
o YAML interpretaria como outro tipo. Chave com valor nulo é **omitida**, não emitida como
`null` (`paginas` some quando não há página).

O path e a mensagem de commit **não mudam** (D-E): seguem `leitura: r42` e
`Leituras/<data> - leitura-r<id>-<hash>.md`.

**Idempotência preservada:** `/draft` reusa o draft salvo quando o digest bate
(`main.py:1237`). O frontmatter deriva de `livro`, `pagina_inicial`, `pagina_final` e `inicio`
— os três primeiros já são entradas do digest e o quarto é imutável. Mesmo digest, mesmo
frontmatter.

## O recap

No compile, depois da nota aprovada ser gravada, uma segunda chamada curta ao Hermes devolve
2–4 linhas: onde a leitura parou e o fio condutor. Guardado em `reading_sessions.recap`.

**Sai do payload estruturado sem citações** (D-I) — o mesmo `model_chunks` que o
`READING_FRAME` recebe (`hermes_client.py:315-317`), com o mesmo enquadramento
`<sessao>...</sessao>` de dado não confiável. As citações continuam fora do alcance do modelo,
como já estão hoje.

**Best-effort, pelo padrão que já existe:** o Anki no compile já é assim (`main.py:1290` —
"Anki é best-effort e nunca reabre uma compilação já publicada"). Hermes falhou → a nota está
gravada, os cards nasceram, `recap` fica `NULL`, a estante não mostra recap. Nada trava.

**Por que não precisa de portão humano:** o recap não vai para o vault, não vira card, não
sai do app. É legenda de navegação, regenerável e descartável. A lei 3 guarda artefato
permanente e tarefa; o recap não é nenhum dos dois.

**Chamada separada, não campo a mais no `READING_FRAME`:** aquele frame devolve Markdown puro
(`hermes_client.py:290`) e as citações são coladas por código depois. Transformar em JSON
acrescentaria um modo de falha de parse no caminho que grava o artefato permanente. O recap é
acessório; não paga esse risco.

## Anki: formato do TSV

`anki.tsv()` ganha a quinta coluna (deck) e o arquivo ganha os headers do Anki. Um export
carrega cards de obras diferentes, então precisa ser **deck por linha**, não `#deck:` fixo
por arquivo.

**Verificação bloqueante antes de implementar** (não é "TBD": é um teste com dois desfechos
já decididos). Importar um TSV de fixture com header de coluna de deck na versão de Anki que
o Leo usa:

- **Suporta** → header no arquivo, quinta coluna por linha, um export só.
- **Não suporta** → **um arquivo por deck**, cada um com `#deck:` fixo no topo.
  `claim_anki_export` agrupa por deck e `exportar_anki` devolve N arquivos.

O contrato só fecha depois desse teste; os bytes exatos do header entram na spec junto com o
resultado. Card antigo com `deck=''` cai no deck padrão do Anki — a ser confirmado no mesmo
teste, e não assumido.

## Migração

Segue o padrão que já existe em `init_db` (`store.py:277-288`): `PRAGMA table_info` +
`ALTER TABLE` condicional. Banco existente e banco novo convergem para o mesmo schema.

1. `CREATE TABLE IF NOT EXISTS books (...)`.
2. `reading_sessions`: `ADD COLUMN book_id INTEGER` se ausente.
3. `reading_sessions`: `ADD COLUMN recap TEXT` se ausente.
4. `CREATE INDEX IF NOT EXISTS idx_reading_sessions_book`.
5. Recuperação de lease velho: `UPDATE books SET status='lendo' WHERE status='terminando'
   AND updated < claim_cutoff`, junto das que já existem (`store.py:266-275`).
6. `anki_cards` **não muda** — `deck` já existe.

Sem backfill (D-D): linhas antigas ficam com `book_id NULL` e `recap NULL`.

## Testes

**Migração**
- Partindo de um banco no schema anterior (fixture), `init_db` cria `books`, acrescenta as
  colunas e o índice; rodar duas vezes não quebra.
- Lease velho em `terminando` volta para `lendo`.

**Obra e slug**
- Mesmo título duas vezes → `created:false`, uma linha só.
- "Sapiens" e "sapiens " → mesma obra. **"C", "C++" e "C#" → três obras.**
- Título só de espaços → 422 `titulo_invalido`, nada gravado.

**Derivadas**
- `pagina_atual` ignora `pending` e `discarded`.
- Sessão mais recente com `pagina_final NULL` → cai na anterior que tem.
- Obra sem sessão compilada → `pagina_atual: null` sem quebrar.
- **Releitura:** sessão do ciclo 1 termina na 300, `reabrir`, sessão do ciclo 2 termina na
  120 → `pagina_atual == 120`.

**Sessão**
- `book_id` válido → `livro` da sessão é o título canônico, mesmo com `livro` divergente no
  corpo.
- `book_id` inexistente → 422, nenhuma sessão criada.
- Sem `book_id` → caminho antigo intacto (regressão dos testes de leitura que já existem).
- Renomear a obra depois → `source_digest` de sessão já compilada segue válido.

**terminar / reabrir**
- Duas chamadas concorrentes → uma tarefa, a outra 409.
- ClickUp indisponível → obra volta a `lendo`, 502, nenhuma tarefa órfã.
- Crash entre criar no ClickUp e persistir → a chamada seguinte reconcilia pelo marker, não
  duplica.
- terminar → reabrir → terminar: **duas** tarefas, a do ciclo 2 listando só as notas do
  ciclo 2.

**Frontmatter**
- `draft_md` staged **já contém** o frontmatter; o gravado no vault é idêntico ao aprovado.
- Título com `"`, `:`, `#`, `---`, quebra de linha, e o título `yes` → YAML válido, valor
  preservado como string.
- Sem `pagina_final` → a chave `paginas` **não aparece**.
- Path e mensagem de commit inalterados (guarda da lei 7).
- Mesmo snapshot chamado duas vezes → mesmo `draft_md`, sem segunda chamada ao Hermes.

**Anki**
- Compile com `book_id` → cards gravados com `deck='Leitura::<titulo>'`.
- Compile sem `book_id` → `deck=''`.
- **Card do modelo trazendo `deck` no dict → o valor do modelo é descartado; vale o do
  código.**
- `anki.tsv()` serializa a coluna de deck; card antigo com deck vazio ainda sai íntegro.
- Retry de sessão já compilada não reinsere card nem duplica deck.

**Recap**
- Falha do Hermes no recap não impede vault nem cards (espelha o teste de falha do Anki).
- **O payload do recap não contém nenhum chunk de hook `quote`.**

## Fora de escopo

Capa, ISBN, total de páginas, progresso em %, rating, "quero ler", importar do Goodreads,
busca de metadados. A estante é uma lista de o que você está lendo e onde parou.
