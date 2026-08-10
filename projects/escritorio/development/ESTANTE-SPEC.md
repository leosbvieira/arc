---
artifact: skill-spec
capability: escritorio
skill: estante (lane "Leitura")
status: proposed
date: 2026-08-09
revision: 3 (duas rodadas de revisão hostil GPT-5.6 Sol, 2026-08-09)
source_refs:
  - READING-STAGING-SPEC.md
  - AETERNUM-SPEC.md
  - CAPTURE-GRAMMAR-SPEC.md
  - "brainstorm 2026-08-09 (Leo + Claude): livro como entidade"
  - "revisão hostil rodada 1 (GPT-5.6 Sol, high): 15 achados"
  - "revisão hostil rodada 2 (GPT-5.6 Sol, high): 9 resolvidos, 5 parciais, 9 achados novos"
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
(`store.py:1266`). Sessões compiladas até são lidas de volta — no reconcile e nos retries
(`main.py:1188`). O que nunca existiu é leitura desse dado **como progresso por obra**.

**Simetria que motivou a spec:** a nota da sessão já tem staging e vai pro vault; os cards já
têm staging e vão pro Anki. A **obra** — o eixo em torno do qual as duas coisas fazem sentido
— não existia em lugar nenhum.

## Decisões

- **D-A — tabela `books` mínima, progresso derivado.** A tabela guarda **só o que sessão
  nenhuma consegue carregar**: título, slug, status, ciclo. Página atual e data da última
  leitura são **derivadas** das sessões compiladas. Sem capa, sem ISBN, sem total de páginas,
  sem nota.
- **D-B — recap gerado no fim da sessão anterior, não no começo da próxima.** O Hermes já é
  chamado no compile. O recap nasce ali e fica guardado na sessão; a próxima sessão só lê.
- **D-C — tudo é obra.** Artigo e capítulo avulso entram na mesma tabela.
- **D-D — começar do zero.** O histórico fica com `book_id NULL`.
- **D-E — lei 7 preservada.** Paths do vault seguem neutros; o título entra no frontmatter.
- **D-F — deck `Leitura::<Título>`.** Subdeck deixa escolher na revisão: `Leitura` puxa de
  todas as obras, `Leitura::Sapiens` de uma.
- **D-G — terminar o livro vira tarefa, não tela.** Tarefa no ClickUp em Staging (lei 3) com
  template de resumão apontando pras notas do ciclo.

### Acrescentadas na revisão 2

- **D-H — o frontmatter entra ANTES do staging.** A revisão 1 mandava colar na hora de gravar
  no vault. Isso **furava o portão humano**: `main.py:1319` lê `draft_md` e `main.py:1332`
  grava exatamente esse texto; o `source_digest` (`main.py:1327`) existe para garantir que o
  publicado é o aprovado.
- **D-I — o recap não vê citações.** A nota tem citações coladas por código
  (`hermes_client.py:346`) e o payload do modelo as exclui de propósito (`:310-317`). Gerar
  recap "a partir da nota" desfazia esse isolamento.
- **D-J — página atual é a da sessão mais recente, não o máximo.** `MAX` mente em releitura.
- **D-K — ciclo de leitura.** `reabrir` abre um ciclo novo: a página recomeça e o segundo
  resumão cobre o segundo ciclo.

### Acrescentadas na revisão 3

- **D-L — o ciclo é copiado, não inferido por tempo.** A revisão 2 definia o ciclo por
  `inicio >= ciclo_inicio`. Errado: `inicio` **vem do cliente** (`store.py:924`,
  `readingApi.ts:98`). Celular com relógio atrasado criaria uma sessão legítima que ficaria
  fora do ciclo para sempre. Agora `reading_sessions.book_ciclo` é **copiado de `books.ciclo`
  na criação**, dentro da mesma transação, e o agrupamento é por igualdade.
- **D-M — terminar fecha a admissão.** Obra `terminado`/`terminando` não aceita sessão nova, e
  `terminar` recusa enquanto houver sessão não terminal daquele ciclo. Sem isso o resumão
  nasceria sem uma nota que ainda estava em voo.
- **D-N — idempotência antes do claim.** A revisão 2 punha o claim no passo 1, então um retry
  de chamada bem-sucedida cujo response se perdeu batia em `book_ja_terminado` e nunca chegava
  ao `{created:false}`. A verificação de `resumo_ciclo` vem **primeiro**.
- **D-O — o draft tem versão de formato.** Draft staged antes do deploy tem digest válido,
  então `/draft` o reusaria (`main.py:1237`) e `/compile` publicaria sem frontmatter. `draft_fmt`
  força a regeneração e uma nova aprovação.

## Bug encontrado: `deck` é descartado em três pontos

A coluna `anki_cards.deck` **existe** (`store.py:201`, default `''`) e o PATCH escreve nela
(`main.py:828`). Mas o valor nunca chega lá:

1. `store.py:2563` — `_normalizar_anki_cards` monta `{"frente": frente}` e só itera
   `("meaning", "example", "hook")`. Outras chaves caem.
2. `store.py:2584` — o `INSERT` não inclui `deck`.
3. `anki.py:10` — o TSV serializa quatro campos, e `deck` não é um deles.

**O descarte em (1) é correto e fica.** `_normalizar_anki_cards` recebe a proposta **do
modelo**, e o modelo não tem autoridade para escolher deck — se viajasse como campo do dict,
uma injeção na leitura direcionaria cards para qualquer deck. O deck é **determinado por
código** a partir do `book_id` da sessão e viaja como **parâmetro de função**:

```
_suggest_anki_once(session_id, notas, deck)
  → finish_anki_suggestion(session_id, cards, deck="")
    → _insert_anki_cards(con, cards, session_id, deck="")
```

`add_anki_cards(cards, session_id=None, deck="")` ganha o mesmo parâmetro, **com default**,
porque `/anki/sugerir` chama os dois diretamente (`main.py:2079` e `:2081`) e não passa por
`_suggest_anki_once`. Esse endpoint resolve o deck do mesmo jeito quando recebe `session_id`;
sem `session_id`, deck vazio. O retry de sessão já compilada (`main.py:1188`) devolve cards
via `list_anki_cards_for_session` e não reinsere — não precisa de deck.

## Modelo de dados

```sql
CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  titulo TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'lendo',   -- 'lendo' | 'terminando' | 'terminado'
  ciclo INTEGER NOT NULL DEFAULT 1,
  resumo_task_id TEXT,
  resumo_ciclo INTEGER,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reading_sessions_book
  ON reading_sessions(book_id, book_ciclo, fim);
```

`reading_sessions` ganha três colunas nullable: `book_id INTEGER`, `book_ciclo INTEGER`,
`recap TEXT`, mais `draft_fmt INTEGER` (D-O).

### O ciclo é copiado na criação (D-L)

`books.ciclo` começa em 1 e é incrementado por `reabrir`. Na criação da sessão, o valor
corrente é **copiado** para `reading_sessions.book_ciclo` dentro da mesma transação
`BEGIN IMMEDIATE` que já existe em `create_reading_session` (`store.py:930`). As sessões do
ciclo atual são `WHERE book_id = ? AND book_ciclo = ?` — comparação de inteiro, imune ao
relógio do celular.

### Slug: dedup, não identidade

Normaliza **só** caixa, acentos e espaços em excesso. **Pontuação é preservada**: descartá-la
colapsaria "C", "C++" e "C#" numa obra só. Slug vazio (título só de espaço/controle) → 422
`titulo_invalido`.

`slug` é `UNIQUE`, e isso significa que duas obras distintas de título idêntico não coexistem.
**É aceito de propósito**: o título é texto livre, então a desambiguação é digitar
"Sapiens (Harari)". Uma tela de confirmação de duplicata custa mais do que o caso vale, e o
caso é duas obras homônimas sendo lidas ao mesmo tempo pela mesma pessoa.

### Derivadas (uma fonte de verdade só)

Sobre as sessões `status='compiled'` com `book_ciclo = books.ciclo`:

- `pagina_atual` = `pagina_final` da sessão mais recente por `fim DESC, id DESC` **que tenha
  `pagina_final NOT NULL`**. Sessão recente sem página final não apaga o progresso: cai na
  anterior que tenha. Sem nenhuma → `null`, e a tela mostra campo vazio, não "pág. null".
- `ultima_sessao` = `MAX(fim)`.
- `recap` = o `recap` da sessão compilada mais recente do ciclo.

## Sessão: uma fonte de verdade para o título

`POST /reading/sessions` aceita `book_id` opcional. Com `book_id`, dentro da transação de
`create_reading_session`:

- **valida o status da obra** (D-M): `terminado` ou `terminando` → 409 `book_nao_aceita_sessao`,
  nenhuma sessão criada. O caminho legítimo para reler é `reabrir`.
- **copia o `titulo` canônico** para `reading_sessions.livro` e **`books.ciclo`** para
  `book_ciclo`;
- **ignora** qualquer `livro` que venha no corpo — o servidor manda;
- `book_id` inexistente → 422 `book_nao_encontrado`.

**Retry:** `create_reading_session` já é idempotente por `client_key` e devolve a linha
original com `created:false` (`store.py:935-937`). Se o retry trouxer `book_id` diferente, a
**sessão gravada vence** e o corpo é ignorado — mesma regra que já vale hoje para `livro`.
Nenhuma sessão troca de obra depois de criada.

Sem `book_id`, o comportamento é o de hoje. O caminho antigo não quebra.

**Por que copiar o título em vez de referenciar:** ele entra no `source_digest`
(`main.py:1313`). Copiando na criação, renomear a obra depois **não reescreve o histórico**
nem invalida digests de sessões compiladas.

**Por que `book_id` NÃO entra no `source_digest`:** a única coisa que a obra determina é o
título, e o título já está no digest, copiado e imutável. Deck e frontmatter derivam desse
mesmo título. Acrescentar `book_id` invalidaria drafts antigos sem cobrir nada novo. `book_id`
**entra** no `ReadingSession` devolvido pela API (o app precisa para a tela) e no
`ReadingSnapshot` como campo informativo, não comparado.

## Endpoints

- `GET /reading/books?status=lendo` → `[{id, titulo, status, ciclo, pagina_atual,
  ultima_sessao, sessoes_n, recap}]`. Uma query com agregação, sem N+1.
- `POST /reading/books` `{titulo}` → cria ou **reusa** a obra de mesmo slug. Em
  `BEGIN IMMEDIATE`, `INSERT ... ON CONFLICT(slug) DO NOTHING` seguido de `SELECT` da linha
  canônica — duas chamadas simultâneas para "Sapiens" devolvem a mesma obra, uma com
  `created:true` e outra com `created:false`, nunca `UNIQUE constraint failed`. É o mesmo
  padrão de `create_reading_session` (`store.py:930`).
- `POST /reading/books/{id}/reabrir` → transição condicional:
  `UPDATE books SET status='lendo', ciclo=ciclo+1, updated=? WHERE id=? AND status='terminado'`.
  `rowcount = 0` → 409 (`book_ja_lendo` ou `book_terminando`, conforme o status corrente).
  Dois toques simultâneos: só um incrementa. Não mexe na tarefa do ciclo anterior.
- `POST /reading/books/{id}/terminar` → abaixo.

### `terminar`: idempotência primeiro, claim depois, ClickUp antes da escrita

Ordem corrigida na revisão 3 (D-N). Tudo de (1) a (3) dentro de um `BEGIN IMMEDIATE`:

1. **Já terminado neste ciclo?** `resumo_ciclo == ciclo` → devolve a tarefa existente com
   `created:false`, sem tocar no ClickUp. **Esta verificação vem antes do claim** — senão o
   retry de uma chamada bem-sucedida cujo response se perdeu bateria em `book_ja_terminado`.
2. **Sessão aberta?** (D-M) Qualquer `reading_sessions` do ciclo em `pending` ou `compiling` →
   409 `book_com_sessao_aberta`, com os ids. Termine a sessão, depois termine a obra.
3. **Claim**, aceitando retomada de lease velho sem esperar o `init_db`:
   `UPDATE books SET status='terminando', updated=? WHERE id=? AND (status='lendo' OR
   (status='terminando' AND updated < claim_cutoff))`. `rowcount = 0` → 409. Dois toques
   simultâneos: só um passa.
4. **Reconciliar antes de criar:** `find_task_by_marker` com o marker do ciclo, como a captura
   faz (`capture_pipeline.py:175-182`). Cobre o crash entre criar no ClickUp e persistir o id.
5. **Criar** em Staging se o marker não existir.
6. **Persistir** `status='terminado'`, `resumo_task_id`, `resumo_ciclo = ciclo` numa **única
   transação local**.
7. **Falha em (4) ou (5):** release → `status='lendo'`, 502 `clickup_indisponivel`. A obra
   **nunca** sai da estante sem tarefa criada.

**Sobre lease velho:** o `claim_cutoff` de (3) usa `CLAIM_STALE_SECONDS`, e o `init_db` também
recupera (migração, item 5). É exatamente o mecanismo que `claim_reading_compile`
(`store.py:1178`, `:263-270`) usa para a **escrita no vault**. Se basta para o artefato
permanente, basta para uma tarefa de ClickUp — não vale um token de fencing aqui.

**Idempotência por ciclo:** terminar → reabrir → terminar cria duas tarefas, a do ciclo 2
listando só as notas do ciclo 2.

## Template do resumão

Título da tarefa: `Resumo de leitura — {titulo}` (ciclo 1) ou
`Resumo de leitura — {titulo} (releitura {ciclo})` para `ciclo > 1`.

Descrição:

```markdown
[book-summary:{book_id}:{ciclo}]

{n} sessões · páginas {min}–{max} · de {primeira_data} a {ultima_data}

## Notas da obra
- 2026-07-02 · p. 12–58 · `Leituras/2026-07-02 - leitura-r38-<hash>.md`
- 2026-07-09 · p. 58–110 · `Leituras/2026-07-09 - leitura-r41-<hash>.md`

## O que eu aprendi

## O que mudou de opinião

## O que vou aplicar

## O que ficou em aberto
```

- O **marker é a primeira linha**, e é o que `find_task_by_marker` procura (passo 4).
- As notas vêm das sessões `compiled` **do ciclo**, ordenadas por `fim ASC`. O link é o
  `vault_path` já gravado — path neutro, sem título (lei 7 intacta mesmo dentro do ClickUp).
- `páginas {min}–{max}` só aparece quando ao menos uma sessão do ciclo tem os dois limites;
  senão a linha traz só contagem e datas.
- Os cabeçalhos vão vazios de propósito: quem responde é você.

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
- **`✓`** marca terminado. Confirmação: *"Terminar Sapiens? Cria a tarefa de resumão em
  Staging."* Durante a chamada, linha desabilitada com spinner. Erro → mensagem inline, linha
  volta ao normal (o servidor já liberou o claim). 409 `book_ja_terminado` → recarrega a
  estante em vez de mostrar erro. 409 `book_com_sessao_aberta` → *"Termine a sessão de leitura
  antes"*, com atalho para a sessão pendente.
- **`+ novo livro`** abre o campo de texto de hoje, que chama `POST /reading/books` antes de
  começar a sessão.
- **`ver obras terminadas`** lista `status=terminado`, cada uma com **reabrir** e o link da
  tarefa de resumão. É onde a obra volta pra estante.
- 409 `book_nao_aceita_sessao` ao começar (tela velha, obra terminada em outro lugar) →
  recarrega a estante e avisa que a obra foi terminada.

Quando há `recap`, ele aparece acima do botão, em duas ou três linhas. É texto guardado, não
chamada de modelo — aparece instantâneo.

Estante vazia (o primeiro dia, por D-D) mostra só `+ novo livro`. As sessões pendentes de
"RETOMAR SESSÃO" (`Capture.tsx:1509`) continuam acima e inalteradas — sessão inacabada não é
obra em andamento.

## O frontmatter (dentro do portão)

Em `/draft`, entre `compile_reading` (`main.py:1240`) e `stage_reading_draft` (`:1255`), o
código prepende:

```yaml
---
livro: "Sapiens"
paginas: 190-214
data: 2026-08-09
---
```

Escrito **por código**, nunca pelo modelo: `livro` da tabela, `paginas` da sessão, `data` do
`inicio`. O que você aprova no preview já é o documento completo, e o compile continua gravando
`draft_md` byte-a-byte.

**`paginas` só aparece quando `pagina_inicial` E `pagina_final` existem.** Os outros três
estados (só inicial, só final, nenhuma) **omitem a chave** — não existe `paginas: -42` nem
`paginas: null`. Regra única, sem caso especial.

**Serialização segura, sem dependência nova.** O BFF não tem PyYAML (`requirements.txt`) e não
vale acrescentar por três linhas. Só `livro` é texto livre. Ele sai **sempre como escalar entre
aspas duplas**, com `\` → `\\`, `"` → `\"`, e quebras de linha e caracteres de controle
colapsados em espaço. Aspas sempre presentes resolvem de uma vez `:`, `#`, `---`, e títulos
como `yes` ou `123` que o YAML leria como outro tipo.

**Draft legado (D-O):** `reading_sessions.draft_fmt` guarda a versão do formato. `/draft` só
reusa o draft salvo quando `draft_fmt = 2` **e** o digest bate (`main.py:1237`); draft de
antes do deploy tem `draft_fmt NULL`, é **regenerado com frontmatter** e volta ao preview para
nova aprovação. Sem isso, um draft aprovado antes do deploy publicaria sem frontmatter.

**Idempotência preservada:** o frontmatter deriva de `livro`, `pagina_inicial`, `pagina_final`
e `inicio` — os três primeiros já são entradas do digest e o quarto é imutável. Mesmo digest e
mesmo `draft_fmt`, mesmo frontmatter, sem segunda chamada ao Hermes.

O path e a mensagem de commit **não mudam** (D-E).

## O recap

No compile, depois da nota aprovada ser gravada, uma segunda chamada curta ao Hermes devolve
2–4 linhas: onde a leitura parou e o fio condutor. Guardado em `reading_sessions.recap`.

**Sai do payload estruturado sem citações** (D-I) — o mesmo `model_chunks` que o
`READING_FRAME` recebe (`hermes_client.py:315-317`), com o mesmo enquadramento
`<sessao>...</sessao>` de dado não confiável.

**Best-effort, pelo padrão que já existe:** o Anki no compile já é assim (`main.py:1290`).
Hermes falhou → nota gravada, cards nascidos, `recap` fica `NULL`, a estante não mostra recap.

**Não é regenerável, e a spec não promete que seja.** O buffer é purgado depois do compile
(`store.py:1291`), e a nota que sobra tem as citações coladas — justamente a fonte que D-I
proíbe. Falhou uma vez, aquela sessão fica sem recap para sempre. É aceitável porque o recap é
legenda de navegação: a estante sem ele mostra livro, página e data, que é o essencial.

**Por que não precisa de portão humano:** o recap não vai para o vault, não vira card, não sai
do app. A lei 3 guarda artefato permanente e tarefa; o recap não é nenhum dos dois.

**Chamada separada, não campo a mais no `READING_FRAME`:** aquele frame devolve Markdown puro
(`hermes_client.py:290`) e as citações são coladas por código depois. Virar JSON acrescentaria
um modo de falha de parse no caminho que grava o artefato permanente.

## Anki: formato do TSV — portão antes de implementar

`anki.tsv()` ganha a quinta coluna (deck) e o arquivo ganha headers. Um export carrega cards
de obras diferentes, então precisa ser **deck por linha**, não `#deck:` fixo por arquivo.

**Este é o único ponto da spec que depende de fato externo, e é um portão, não um TBD.** Antes
da primeira linha de código: importar um TSV de fixture com header de coluna de deck na versão
de Anki que o Leo usa. Os dois desfechos já estão decididos:

- **Suporta** → header no arquivo, quinta coluna por linha, um export só.
- **Não suporta** → **um arquivo por deck**, cada um com `#deck:` fixo no topo.
  `claim_anki_export` agrupa por deck e `exportar_anki` devolve N arquivos.

Os bytes exatos do header entram nesta spec junto com o resultado do teste. Card antigo com
`deck=''` cai no deck padrão — confirmado no mesmo teste, não assumido.

## Migração

Padrão de `init_db` (`store.py:277-288`): `PRAGMA table_info` + `ALTER TABLE` condicional.

1. `CREATE TABLE IF NOT EXISTS books (...)`.
2. `reading_sessions`: `ADD COLUMN book_id INTEGER` se ausente.
3. `reading_sessions`: `ADD COLUMN book_ciclo INTEGER` se ausente.
4. `reading_sessions`: `ADD COLUMN recap TEXT` se ausente.
5. `reading_sessions`: `ADD COLUMN draft_fmt INTEGER` se ausente.
6. `CREATE INDEX IF NOT EXISTS idx_reading_sessions_book`.
7. Lease velho: `UPDATE books SET status='lendo' WHERE status='terminando' AND updated <
   claim_cutoff`, junto das que já existem (`store.py:266-275`).
8. `anki_cards` **não muda** — `deck` já existe.

Sem backfill (D-D): linhas antigas ficam com `book_id`, `book_ciclo`, `recap` e `draft_fmt`
todos `NULL`.

## Testes

**Migração**
- De um banco no schema anterior (fixture): `init_db` cria `books`, acrescenta as quatro
  colunas e o índice; rodar duas vezes não quebra.
- Lease velho em `terminando` volta para `lendo`.

**Obra e slug**
- Mesmo título duas vezes → `created:false`, uma linha só.
- "Sapiens" e "sapiens " → mesma obra. **"C", "C++" e "C#" → três obras.**
- Título só de espaços → 422 `titulo_invalido`, nada gravado.
- Duas criações concorrentes do mesmo título → uma obra, sem `UNIQUE constraint failed`.

**Ciclo (D-L)**
- Sessão criada com `inicio` **anterior** ao `reabrir` (relógio do celular atrasado) ainda
  entra no ciclo corrente, porque `book_ciclo` foi copiado.
- **Releitura:** sessão do ciclo 1 termina na 300, `reabrir`, sessão do ciclo 2 termina na 120
  → `pagina_atual == 120`.
- `reabrir` concorrente: dois toques → `ciclo` incrementa uma vez, o outro 409.
- `reabrir` de obra em `lendo` → 409, `ciclo` intacto.

**Derivadas**
- `pagina_atual` ignora `pending` e `discarded`, e ignora sessão de outro ciclo.
- Sessão mais recente com `pagina_final NULL` → cai na anterior que tem.
- Obra sem sessão compilada → `pagina_atual: null` sem quebrar.

**Sessão**
- `book_id` válido → `livro` é o título canônico, mesmo com `livro` divergente no corpo;
  `book_ciclo` == `books.ciclo`.
- `book_id` de obra `terminado` ou `terminando` → 409, nenhuma sessão criada.
- `book_id` inexistente → 422, nenhuma sessão criada.
- Retry da mesma `client_key` com `book_id` diferente → devolve a sessão original, `book_id`
  inalterado, `created:false`.
- Sem `book_id` → caminho antigo intacto (regressão dos testes de leitura existentes).
- Renomear a obra depois → `source_digest` de sessão compilada segue válido.

**terminar / reabrir**
- Retry de chamada bem-sucedida (response perdido) → `{created:false}` com a tarefa existente,
  **não** 409.
- Duas chamadas concorrentes → uma tarefa, a outra 409.
- Sessão `pending` do ciclo → 409 `book_com_sessao_aberta`, nenhuma tarefa criada.
- ClickUp indisponível → obra volta a `lendo`, 502, nenhuma tarefa órfã.
- Crash entre criar no ClickUp e persistir → a chamada seguinte reconcilia pelo marker.
- Claim velho (`terminando` além do cutoff) → a chamada seguinte retoma sem esperar `init_db`.
- terminar → reabrir → terminar: **duas** tarefas, a do ciclo 2 listando só as notas do ciclo 2.
- A descrição da tarefa começa com o marker e lista as notas por `fim ASC`.

**Frontmatter**
- `draft_md` staged **já contém** o frontmatter; o gravado no vault é idêntico ao aprovado.
- Título com `"`, `:`, `#`, `---`, quebra de linha, e o título `yes` → YAML válido, valor
  preservado como string.
- As quatro combinações de página: só ambas emitem `paginas`; as outras três **omitem a chave**.
- Draft legado (`draft_fmt NULL`) com digest válido → **regenerado** com frontmatter, não
  reusado; o preview volta para aprovação.
- Mesmo snapshot com `draft_fmt = 2` → mesmo `draft_md`, sem segunda chamada ao Hermes.
- Path e mensagem de commit inalterados (guarda da lei 7).

**Anki**
- Compile com `book_id` → cards com `deck='Leitura::<titulo>'`.
- Compile sem `book_id` → `deck=''`.
- **Card do modelo trazendo `deck` no dict → o valor do modelo é descartado; vale o do código.**
- `/anki/sugerir` sem `session_id` → `deck=''`, sem erro de assinatura.
- `anki.tsv()` serializa a coluna de deck; card antigo com deck vazio ainda sai íntegro.
- Retry de sessão já compilada não reinsere card nem duplica deck.

**Recap**
- Falha do Hermes no recap não impede vault nem cards (espelha o teste de falha do Anki).
- **O payload do recap não contém nenhum chunk de hook `quote`.**

## Fora de escopo

Capa, ISBN, total de páginas, progresso em %, rating, "quero ler", importar do Goodreads,
busca de metadados, duas obras homônimas simultâneas. A estante é uma lista de o que você está
lendo e onde parou.
