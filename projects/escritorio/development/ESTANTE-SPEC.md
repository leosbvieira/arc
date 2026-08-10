---
artifact: skill-spec
capability: escritorio
skill: estante (lane "Leitura")
status: proposed
date: 2026-08-09
revision: 4 (três rodadas de revisão hostil GPT-5.6 Sol; escopo fatiado)
scope: "fatia 1 de 3 — estante, ciclo, progresso, deck. ClickUp e recap adiados."
source_refs:
  - READING-STAGING-SPEC.md
  - AETERNUM-SPEC.md
  - CAPTURE-GRAMMAR-SPEC.md
  - "brainstorm 2026-08-09 (Leo + Claude): livro como entidade"
  - "revisão hostil r1/r2/r3 (GPT-5.6 Sol, high): ~30 achados; r3 recomendou fatiar"
implements: "livro como entidade: retomar de onde parou, agrupar por obra, deck por obra"
---

# SKILL SPEC — estante (lane "Leitura"), fatia 1

Promove **livro** de string redigitada a **entidade**. Hoje a lane Leitura pergunta "o que
você vai ler?" num campo de texto livre (`Capture.tsx:1529`) e a página inicial você digita
de memória. Nada se acumula por obra: nem o ponto onde parou, nem os comentários, nem os
cards do Anki.

O dado para responder "em que página eu estava" **já está gravado**. `reading_sessions`
guarda `livro`, `pagina_inicial`, `pagina_final` e a linha **sobrevive ao compile**
(`store.py:1266`). Sessões compiladas até são lidas de volta — no reconcile e nos retries
(`main.py:1188`). O que nunca existiu é leitura desse dado **como progresso por obra**.

## Escopo: por que esta spec é uma fatia

As três rodadas de revisão hostil produziram ~30 achados. A distribuição é o argumento: a
esmagadora maioria caiu sobre a **tarefa de resumão no ClickUp** (lease, marker, POST
ambíguo, ciclo vazio, obra presa em `terminando`) e sobre o **export do Anki**. Quase nenhum
caiu sobre a estante em si.

Isso não é acaso — é a parte cara sinalizando que não pertence à mesma entrega.

| Fatia | Entrega | Estado |
|---|---|---|
| **1** | Estante, ciclo, progresso derivado, deck por obra, `terminar` como status local | **esta spec** |
| **2** | Tarefa de resumão no ClickUp ao terminar a obra | adiada, ver no fim |
| **3** | Recap da sessão anterior gerado pelo Hermes | adiada, ver no fim |

Cortar o ClickUp da fatia 1 elimina o status `terminando`, o lease, o token de fencing, o
marker e o tratamento de POST ambíguo — **sete dos dez itens que continuavam abertos na
revisão 3**. `terminar` vira um `UPDATE` condicional numa transação local, e acabou.

## Decisões

- **D-A — tabela `books` mínima, progresso derivado.** A tabela guarda **só o que sessão
  nenhuma consegue carregar**: título, slug, status, ciclo. Página atual e data da última
  leitura são **derivadas** das sessões compiladas. Sem capa, sem ISBN, sem total de páginas,
  sem nota.
- **D-C — tudo é obra.** Artigo e capítulo avulso entram na mesma tabela.
- **D-D — começar do zero.** O histórico fica com `book_id NULL`.
- **D-E — lei 7 preservada.** Paths do vault seguem neutros; o título entra no frontmatter.
- **D-F — deck `Leitura::<Título>`.** Subdeck deixa escolher na revisão: `Leitura` puxa de
  todas as obras, `Leitura::Sapiens` de uma.
- **D-H — o frontmatter entra ANTES do staging.** Colar na hora de gravar no vault **furava o
  portão humano**: `main.py:1319` lê `draft_md` e `main.py:1332` grava exatamente esse texto;
  o `source_digest` (`main.py:1327`) existe para garantir que o publicado é o aprovado.
- **D-J — página atual é a da sessão mais recente, não o máximo.** `MAX` mente em releitura.
- **D-K — ciclo de leitura.** `reabrir` abre um ciclo novo: a página recomeça do zero.
- **D-L — o ciclo é copiado, não inferido por tempo.** `inicio` **vem do cliente**
  (`store.py:924`, `readingApi.ts:98`), então definir o ciclo por janela temporal deixaria
  uma sessão legítima de celular atrasado fora do ciclo para sempre. `book_ciclo` é copiado
  de `books.ciclo` na criação, na mesma transação, e o agrupamento é por igualdade de inteiro.
- **D-M — terminar fecha a admissão.** Obra `terminado` não aceita sessão nova, e `terminar`
  recusa enquanto houver sessão não terminal do ciclo.
- **D-O — o draft tem versão de formato.** Draft staged antes do deploy tem digest válido,
  então `/draft` o reusaria (`main.py:1237`) e `/compile` publicaria sem frontmatter.
- **D-P — o servidor carimba o tempo que ordena as derivadas.** A revisão 3 consertou o ciclo
  e deixou passar que **`fim` também vem do cliente** (`main.py:1299`, `ReadingCompileIn`) —
  a mesma doença, no ordenador. Ordenar por `fim DESC` faria um celular atrasado apontar a
  sessão errada como "a mais recente". `reading_sessions.compiled_at` é carimbado pelo
  servidor em `finish_reading_compile` e é **ele** que ordena. `fim` continua como metadado do
  evento, para exibição e duração.
- **D-Q — sem `terminando`, sem lease.** `terminar` deixa de ter efeito externo (fatia 2), e
  com isso vira um `UPDATE` condicional. Não há claim para recuperar, nem worker velho para
  cercar, nem POST ambíguo para reconciliar.

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
  status TEXT NOT NULL DEFAULT 'lendo',   -- 'lendo' | 'terminado'
  ciclo INTEGER NOT NULL DEFAULT 1,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reading_sessions_book
  ON reading_sessions(book_id, book_ciclo, compiled_at);
```

`reading_sessions` ganha três colunas nullable: `book_id INTEGER`, `book_ciclo INTEGER`,
`compiled_at REAL`, mais `draft_fmt INTEGER`.

Não há `resumo_task_id`, `resumo_ciclo` nem status `terminando`: são da fatia 2.

### O ciclo é copiado na criação (D-L)

`books.ciclo` começa em 1 e é incrementado por `reabrir`. Na criação da sessão, o valor
corrente é **copiado** para `reading_sessions.book_ciclo` dentro da transação
`BEGIN IMMEDIATE` que já existe em `create_reading_session` (`store.py:930`). As sessões do
ciclo atual são `WHERE book_id = ? AND book_ciclo = ?` — comparação de inteiro, imune ao
relógio do celular.

### Slug: dedup, não identidade

Normaliza **só** caixa, acentos e espaços em excesso. **Pontuação é preservada**: descartá-la
colapsaria "C", "C++" e "C#" numa obra só. Slug vazio (título só de espaço/controle) → 422
`titulo_invalido`.

`slug` é `UNIQUE`, então duas obras distintas de título idêntico não coexistem. **Aceito de
propósito**: o título é texto livre, a desambiguação é digitar "Sapiens (Harari)", e o caso é
duas obras homônimas sendo lidas ao mesmo tempo pela mesma pessoa.

### Derivadas (uma fonte de verdade só)

Sobre as sessões `status='compiled'` com `book_ciclo = books.ciclo`, **ordenadas por
`compiled_at DESC, id DESC`** (D-P):

- `pagina_atual` = `pagina_final` da primeira sessão dessa ordem **que tenha `pagina_final NOT
  NULL`**. Sessão recente sem página final não apaga o progresso: cai na anterior que tenha.
  Sem nenhuma → `null`, e a tela mostra campo vazio, não "pág. null".
- `ultima_sessao` = `MAX(compiled_at)`. É o que a tela mostra como "há 3 dias".
- `sessoes_n` = contagem das sessões compiladas do ciclo.

`compiled_at` é carimbado em `finish_reading_compile` (`store.py:1254`) com o relógio do
servidor. Sessões compiladas antes da migração ficam com `compiled_at NULL` — e como só
entram nas derivadas as que têm `book_ciclo` (portanto criadas depois do deploy), nenhuma
derivada lê `NULL`.

## Sessão: uma fonte de verdade para o título

`POST /reading/sessions` aceita `book_id` opcional. Com `book_id`, dentro da transação de
`create_reading_session`:

- **valida o status da obra** (D-M): `terminado` → 409 `book_nao_aceita_sessao`, nenhuma
  sessão criada. O caminho legítimo para reler é `reabrir`.
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
  ultima_sessao, sessoes_n}]`. Uma query com agregação, sem N+1. `status=terminado` devolve o
  mesmo shape.
- `POST /reading/books` `{titulo}` → cria ou **reusa** a obra de mesmo slug. Em
  `BEGIN IMMEDIATE`, `INSERT ... ON CONFLICT(slug) DO NOTHING` seguido de `SELECT` da linha
  canônica — duas chamadas simultâneas para "Sapiens" devolvem a mesma obra, uma com
  `created:true` e outra com `created:false`, nunca `UNIQUE constraint failed`. Mesmo padrão
  de `create_reading_session` (`store.py:930`).
- `POST /reading/books/{id}/terminar` → em `BEGIN IMMEDIATE`:
  1. Sessão do ciclo em `pending` ou `compiling` (D-M) → 409 `book_com_sessao_aberta`, com os
     ids. Termine a sessão, depois termine a obra.
  2. `UPDATE books SET status='terminado', updated=? WHERE id=? AND status='lendo'`.
     `rowcount = 0` → 409 `book_ja_terminado`.

  Sem efeito externo, sem lease, sem reconciliação (D-Q). O retry que perdeu o response recebe
  409 `book_ja_terminado`, e o app trata isso como sucesso: recarrega a estante. **Não há nada
  para ser idempotente a respeito** — nenhuma tarefa foi criada, nenhum recurso externo mudou.
- `POST /reading/books/{id}/reabrir` →
  `UPDATE books SET status='lendo', ciclo=ciclo+1, updated=? WHERE id=? AND status='terminado'`.
  `rowcount = 0` → 409 `book_ja_lendo`. Dois toques simultâneos: só um incrementa.

Terminar uma obra sem nenhuma sessão é **permitido**: é assim que você tira da estante uma
obra criada por engano. (Na fatia 2 isso exige regra própria, porque o resumão de ciclo vazio
não tem datas — está anotado lá.)

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
- **`✓`** marca terminado. Confirmação: *"Terminar Sapiens?"*. Durante a chamada, linha
  desabilitada com spinner. Erro → mensagem inline, linha volta ao normal. 409
  `book_ja_terminado` → recarrega a estante, sem erro. 409 `book_com_sessao_aberta` →
  *"Termine a sessão de leitura antes"*, com atalho para a sessão pendente.
- **`+ novo livro`** abre o campo de texto de hoje, que chama `POST /reading/books` antes de
  começar a sessão.
- **`ver obras terminadas`** lista `status=terminado`, cada uma com **reabrir**.
- 409 `book_nao_aceita_sessao` ao começar (tela velha, obra terminada em outro lugar) →
  recarrega a estante e avisa.

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
estados **omitem a chave** — não existe `paginas: -42` nem `paginas: null`. Regra única.

**Serialização segura, sem dependência nova.** O BFF não tem PyYAML (`requirements.txt`) e não
vale acrescentar por três linhas. Só `livro` é texto livre. Ele sai **sempre como escalar entre
aspas duplas**, com `\` → `\\`, `"` → `\"`, e quebras de linha e caracteres de controle
colapsados em espaço. Aspas sempre presentes resolvem de uma vez `:`, `#`, `---`, e títulos
como `yes` ou `123` que o YAML leria como outro tipo.

**Draft legado (D-O), nos dois endpoints.** `reading_sessions.draft_fmt` guarda a versão do
formato:

- `/draft` só reusa o draft salvo quando `draft_fmt = 2` **e** o digest bate (`main.py:1237`).
  `draft_fmt NULL` → regenera com frontmatter e devolve ao preview.
- **`/compile` exige `draft_fmt = 2`** (`main.py:1319`) → senão, 409 `reading_draft_desatualizado`,
  e o app chama `/draft` de novo e mostra o preview para nova aprovação. Sem isso, um preview
  já aberto no celular durante o deploy publicaria o Markdown antigo: o digest continua válido,
  então nada mais o barraria.

**Idempotência preservada:** o frontmatter deriva de `livro`, `pagina_inicial`, `pagina_final`
e `inicio` — os três primeiros já são entradas do digest e o quarto é imutável. Mesmo digest e
mesmo `draft_fmt`, mesmo frontmatter, sem segunda chamada ao Hermes.

O path e a mensagem de commit **não mudam** (D-E).

## Anki: formato do TSV

`anki.tsv()` ganha a quinta coluna (deck) e o arquivo ganha headers:

```
#separator:tab
#html:false
#deck column:5
```

O deck vai **por linha**, não `#deck:` fixo por arquivo: um export carrega cards de obras
diferentes. `#deck column:N` existe desde o Anki 2.1.55 (fim de 2022); o Anki do Leo é de
2026.

**Célula de deck vazia nunca é emitida.** Card sem obra sai no deck-pai `Leitura`. Isso
elimina a pergunta "o que o Anki faz com uma célula vazia?" em vez de respondê-la — e o
resultado é o certo de qualquer forma: um card de leitura sem obra ainda é um card de leitura.

O banco continua guardando `deck=''` para card sem obra. O gravado diz **o que o sistema
sabe**; o fallback é decisão de **serialização** e mora no `anki.py`. Separar as duas coisas é
o que permitiria, depois, reclassificar cards antigos sem reescrever histórico.

**Nota das revisões:** o revisor manteve este item como "não resolvido" nas três rodadas,
corretamente — enquanto o contrato dependia de testar o comportamento da célula vazia, não
fechava escrevendo spec. O que fechou não foi o teste: foi tirar a dependência do desenho.

## Migração

Padrão de `init_db` (`store.py:277-288`): `PRAGMA table_info` + `ALTER TABLE` condicional.

1. `CREATE TABLE IF NOT EXISTS books (...)`.
2. `reading_sessions`: `ADD COLUMN book_id INTEGER` se ausente.
3. `reading_sessions`: `ADD COLUMN book_ciclo INTEGER` se ausente.
4. `reading_sessions`: `ADD COLUMN compiled_at REAL` se ausente.
5. `reading_sessions`: `ADD COLUMN draft_fmt INTEGER` se ausente.
6. `CREATE INDEX IF NOT EXISTS idx_reading_sessions_book`.
7. `anki_cards` **não muda** — `deck` já existe.

Sem backfill (D-D): linhas antigas ficam com as quatro colunas `NULL`. Nenhuma recuperação de
lease, porque não há lease (D-Q).

## Testes

**Migração**
- De um banco no schema anterior (fixture): `init_db` cria `books`, acrescenta as quatro
  colunas e o índice; rodar duas vezes não quebra.

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

**Derivadas (D-P)**
- Duas sessões do ciclo, a segunda compilada depois mas com **`fim` menor** (relógio
  atrasado) → `pagina_atual` é a da segunda, porque ordena por `compiled_at`.
- `pagina_atual` ignora `pending` e `discarded`, e ignora sessão de outro ciclo.
- Sessão mais recente com `pagina_final NULL` → cai na anterior que tem.
- Obra sem sessão compilada → `pagina_atual: null` sem quebrar.

**Sessão**
- `book_id` válido → `livro` é o título canônico, mesmo com `livro` divergente no corpo;
  `book_ciclo` == `books.ciclo`.
- `book_id` de obra `terminado` → 409, nenhuma sessão criada.
- `book_id` inexistente → 422, nenhuma sessão criada.
- Retry da mesma `client_key` com `book_id` diferente → devolve a sessão original, `book_id`
  inalterado, `created:false`.
- Sem `book_id` → caminho antigo intacto (regressão dos testes de leitura existentes).
- Renomear a obra depois → `source_digest` de sessão compilada segue válido.

**terminar / reabrir**
- Duas chamadas concorrentes de `terminar` → uma vence, a outra 409.
- Sessão `pending` do ciclo → 409 `book_com_sessao_aberta`, status intacto.
- Obra sem sessão nenhuma → `terminar` funciona (remoção de obra criada por engano).
- terminar → reabrir → nova sessão → `book_ciclo == 2`.

**Frontmatter**
- `draft_md` staged **já contém** o frontmatter; o gravado no vault é idêntico ao aprovado.
- Título com `"`, `:`, `#`, `---`, quebra de linha, e o título `yes` → YAML válido, valor
  preservado como string.
- As quatro combinações de página: só ambas emitem `paginas`; as outras três **omitem a chave**.
- Draft legado (`draft_fmt NULL`) com digest válido → `/draft` **regenera**, não reusa.
- **`/compile` com `draft_fmt NULL` e digest válido → 409, nada gravado no vault.**
- Mesmo snapshot com `draft_fmt = 2` → mesmo `draft_md`, sem segunda chamada ao Hermes.
- Path e mensagem de commit inalterados (guarda da lei 7).

**Anki**
- Compile com `book_id` → cards com `deck='Leitura::<titulo>'`.
- Compile sem `book_id` → `deck=''`.
- **Card do modelo trazendo `deck` no dict → o valor do modelo é descartado; vale o do código.**
- `/anki/sugerir` sem `session_id` → `deck=''`, sem erro de assinatura.
- `anki.tsv()` serializa a coluna de deck; card antigo com deck vazio ainda sai íntegro.
- Retry de sessão já compilada não reinsere card nem duplica deck.

## Fatia 2 — tarefa de resumão no ClickUp (adiada)

Ao marcar `terminado`, criar tarefa em Staging (lei 3) com template de resumão apontando pras
notas do ciclo. **Pode ser retroativa**: as obras terminadas na fatia 1 já têm ciclo e
sessões, então a fatia 2 consegue gerar o resumão delas depois.

O que a revisão hostil deixou registrado como pendência desta fatia, para não se perder:

- **Status `terminando` + claim** volta a ser necessário, porque `terminar` passa a ter efeito
  externo. Com ele voltam a recuperação de lease e a questão do fencing.
- **Os `rowcount != 1` da fatia 1 viram ambíguos no momento em que existir um terceiro
  status.** Hoje `terminar_book` e `reabrir_book` devolvem `ja_terminado`/`ja_lendo` para
  qualquer status inesperado, e isso está certo porque só existem dois. Assim que `terminando`
  entrar, um `reabrir` durante o fechamento responderia `ja_lendo` — mentira. As duas funções
  precisam reler o status e discriminar antes de devolver o estado. (Achado do revisor da
  Task 4 na implementação da fatia 1.)
- **POST ambíguo:** se o ClickUp cria a tarefa mas a resposta se perde, liberar para `lendo` é
  errado — uma sessão nova entraria no ciclo e o retry reconciliaria uma tarefa que não a
  contém. A obra deve **ficar em `terminando`** até se provar que nenhuma tarefa foi criada.
  O argumento do revisor procede e derruba a analogia que eu tinha feito com o vault: o vault
  escreve em path determinístico, o POST do ClickUp não é idempotente.
- **Marker** `[book-summary:{book_id}:{ciclo}]` na primeira linha da descrição, para
  `find_task_by_marker` (`capture_pipeline.py:175-182`).
- **Ciclo vazio:** obra terminada sem sessão não tem `primeira_data` nem `ultima_data`. Definir
  o template vazio ou recusar o resumão nesse caso.
- **Páginas parciais:** as linhas `p. X–Y` do template e o agregado `{min}–{max}` precisam dos
  quatro formatos definidos, como o frontmatter já tem.
- **Link da tarefa na API:** `GET /reading/books?status=terminado` precisa devolver
  `resumo_task_id` e o contrato da URL, senão a tela não mostra o link.
- **Obra presa em `terminando`:** precisa aparecer em alguma listagem, com ação de reconciliar.

## Fatia 3 — recap da sessão anterior (adiada)

Segunda chamada ao Hermes no compile, 2–4 linhas sobre onde a leitura parou, guardadas em
`reading_sessions.recap` e mostradas na estante ao começar a próxima sessão. Gerado no fim da
sessão anterior para não custar espera na hora de ler.

Pendências registradas:

- **Sai do payload sem citações:** o mesmo `model_chunks` que o `READING_FRAME` recebe
  (`hermes_client.py:315-317`), com o mesmo enquadramento `<sessao>` de dado não confiável.
  Gerar "a partir da nota pronta" desfaria o isolamento — a nota tem as citações coladas
  (`:346`), e o payload do modelo as exclui de propósito.
- **Best-effort e não regenerável:** o buffer é purgado depois do compile (`store.py:1291`), e
  a nota que sobra tem citações. Falhou uma vez, aquela sessão fica sem recap para sempre.
- **Sem portão humano:** não vai para o vault, não vira card, não sai do app.

## Fora de escopo (todas as fatias)

Capa, ISBN, total de páginas, progresso em %, rating, "quero ler", importar do Goodreads,
busca de metadados, duas obras homônimas simultâneas. A estante é uma lista de o que você está
lendo e onde parou.
