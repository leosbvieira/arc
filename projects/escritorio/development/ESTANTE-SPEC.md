---
artifact: skill-spec
capability: escritorio
skill: estante (lane "Leitura")
status: proposed
date: 2026-08-09
source_refs:
  - READING-STAGING-SPEC.md
  - AETERNUM-SPEC.md
  - CAPTURE-GRAMMAR-SPEC.md
  - "brainstorm 2026-08-09 (Leo + Claude): livro como entidade"
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
(vira `status='compiled'`, `store.py:1266`). É dado órfão — nunca foi lido de volta. Esta
spec fecha o laço.

**Simetria que motivou a spec:** a nota da sessão já tem staging e vai pro vault; os cards
já têm staging e vão pro Anki. A **obra** — o eixo em torno do qual as duas coisas fazem
sentido — não existia em lugar nenhum.

## Decisões (brainstorm 2026-08-09)

- **D-A — tabela `books` mínima, progresso derivado.** A estante nasce de uma tabela, mas
  a tabela guarda **só o que sessão nenhuma consegue carregar**: título, slug, status. Página
  atual e data da última leitura são **derivadas** das sessões compiladas — se virassem colunas,
  divergiriam do histórico no primeiro crash. Sem capa, sem ISBN, sem total de páginas, sem nota.
  (Estante 100% derivada foi descartada: "terminei o livro" é estado que nenhuma sessão carrega,
  e o deck do Anki precisa de identidade estável — não dá pra nomear deck a partir de string
  redigitada.)
- **D-B — recap gerado no fim da sessão anterior, não no começo da próxima.** O Hermes já é
  chamado no compile. O recap nasce ali e fica **guardado na sessão**; a próxima sessão só
  **lê**. Custo zero de espera na hora de começar a ler. (Gerar ao clicar foi descartado:
  pagaria uma chamada de modelo e uma espera a cada abertura da estante.)
- **D-C — tudo é obra.** Artigo e capítulo avulso entram na mesma tabela. Um artigo é só uma
  obra que termina em uma sessão. Um caminho só na tela, sem ramo especial.
- **D-D — começar do zero.** O histórico fica com `book_id NULL`. A estante nasce vazia e
  cresce com as próximas sessões. (Backfill por slug foi descartado: agruparia errado os
  títulos digitados de forma diferente, e a estante nasceria suja de obras já terminadas.)
- **D-E — lei 7 preservada, agrupamento por dentro.** Os paths do vault seguem neutros
  (`Leituras/2026-08-09 - leitura-r42-<hash>.md`). O título da obra entra no **frontmatter**
  da nota, não no caminho. O Obsidian agrupa por Dataview/tag, que lê conteúdo — o histórico
  do git continua sem saber o que você lê. (Pasta por livro foi descartada: entregaria sua
  lista de leitura ao histórico do repositório.)
- **D-F — deck `Leitura::<Título>`.** Subdeck te deixa escolher na hora de revisar: `Leitura`
  puxa de todas as obras, `Leitura::Sapiens` puxa de uma. O TSV sai pro Anki local, não pro
  git — a lei 7 protege o repositório, e o Anki não é o repositório.
- **D-G — terminar o livro vira tarefa, não tela.** Marcar `terminado` cria uma tarefa no
  ClickUp (Staging, como toda tarefa, lei 3) com um template de resumão já apontando pras
  notas daquela obra. O resumão é trabalho seu; o app entrega a moldura e os ponteiros.

## Bug encontrado: `anki_cards.deck` é coluna morta

Não é feature nova, é conserto. A coluna **já existe** (`store.py:201`, default `''`) e o
PATCH já aceita escrever nela (`main.py:828`). Mas:

- o Hermes nunca propõe deck (`ANKI_FRAME`, `hermes_client.py:226` — só `frente`, `meaning`,
  `example`, `hook`);
- nada preenche a partir do livro da sessão;
- **o export TSV descarta a coluna**: `anki.py:10` serializa exatamente quatro campos, e
  `deck` não é um deles.

Ou seja: mesmo preenchendo o deck na mão pelo PATCH, o arquivo que chega no Anki ignorava.
O deck por obra é, em boa parte, ligar um fio que já foi puxado.

## Modelo de dados

```sql
CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  titulo TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'lendo',   -- 'lendo' | 'terminado'
  resumo_task_id TEXT,                    -- id da tarefa ClickUp do resumão
  created REAL NOT NULL,
  updated REAL NOT NULL
);
```

`reading_sessions` ganha `book_id INTEGER` (nullable — o histórico fica NULL, D-D) e
`recap TEXT` (nullable — best-effort, D-B).

**`slug`** é o título normalizado: minúsculas, sem acento, sem pontuação, espaços colapsados.
Serve só pra deduplicar no cadastro — "Sapiens" e "sapiens " não podem virar duas obras.
O `titulo` guarda o que você digitou, e é ele que vai pro deck e pro frontmatter.

**Não são colunas, são derivadas** (uma fonte de verdade só):

- `pagina_atual` = `MAX(pagina_final)` das `reading_sessions` daquela obra com
  `status='compiled'` e `pagina_final NOT NULL`.
- `ultima_sessao` = `MAX(fim)` das mesmas linhas.
- `recap` da estante = o `recap` da sessão compilada mais recente daquela obra.

## Endpoints

- `GET /reading/books?status=lendo` → `[{id, titulo, status, pagina_atual, ultima_sessao,
  sessoes_n, recap}]`. Uma query com agregação, sem N+1.
- `POST /reading/books` `{titulo}` → cria ou **reusa** a obra de mesmo slug. Devolve
  `{book, created}` — mesmo contrato de `createReadingSession`, que já é idempotente por
  `client_key`.
- `POST /reading/books/{id}/terminar` → marca `terminado` e cria a tarefa de resumão.
  **Idempotente**: se `resumo_task_id` já existe, não cria outra. Segue o padrão de
  `capture_queue.clickup_task_id` (`capture_pipeline.py:175`), inclusive a reconciliação por
  marker que cobre o crash entre criar no ClickUp e persistir o id.
- `POST /reading/books/{id}/reabrir` → volta pra `lendo`. Não mexe na tarefa já criada.
- `POST /reading/sessions` ganha `book_id` opcional. Sem ele, o comportamento é o de hoje
  (`livro` como texto solto) — o caminho antigo não quebra.

## Tela

A `Card` de setup da Leitura (`Capture.tsx:1527`) troca o campo livre pela estante:

```
O QUE VOCÊ ESTÁ LENDO?

  Sapiens                        pág. 214 · há 3 dias
  Antifrágil                     pág. 88  · há 2 semanas
  + novo livro
```

Tocar numa obra abre o setup com `livro` e `pagina_inicial` preenchidos — `pagina_inicial`
é o `pagina_atual` derivado, **editável** (você pode ter lido no papel desde então). "Pág.
final" segue como está. `+ novo livro` abre o campo de texto de hoje, que agora chama
`POST /reading/books` antes de começar a sessão.

Quando há `recap`, ele aparece acima do botão, em duas ou três linhas: onde você parou e o
fio que estava seguindo. É texto guardado, não chamada de modelo — aparece instantâneo.

Estante vazia (o estado do primeiro dia, por D-D) mostra só `+ novo livro`. As sessões
pendentes de "RETOMAR SESSÃO" (`Capture.tsx:1509`) continuam onde estão, acima — são outra
coisa: sessão inacabada, não obra em andamento.

## O recap

No compile, depois da nota ficar pronta, uma segunda chamada curta ao Hermes recebe a nota
recém-gerada e devolve 2–4 linhas: onde a leitura parou e o fio condutor. Guardado em
`reading_sessions.recap`.

**Best-effort, pelo padrão que já existe**: o Anki no compile já é assim (`main.py:1290` —
"Anki é best-effort e nunca reabre uma compilação já publicada"). Se o Hermes falhar, a nota
grava, os cards nascem, e o `recap` fica `NULL`. A estante simplesmente não mostra recap
daquela obra. Nada trava.

Chamada separada em vez de um campo a mais na resposta do `READING_FRAME`: aquele frame
devolve **Markdown puro** hoje (`hermes_client.py:290`) e as citações são coladas por código
depois (`hermes_client.py:346`). Transformar em JSON acrescentaria um modo de falha de parse
no caminho que grava o artefato permanente. O recap é acessório; não paga esse risco.

## Anki

No compile, todo card nascido daquela sessão recebe `deck = "Leitura::<titulo>"` quando a
sessão tem `book_id`. Sem `book_id`, `deck` fica `''` como hoje.

`anki.tsv()` ganha a coluna de deck e o arquivo ganha os headers do Anki. Um único export
carrega cards de obras diferentes, então precisa ser **deck por linha** (`#deck column:N`),
não `#deck:` fixo por arquivo. A sintaxe exata e a versão mínima do Anki que a suporta são
**para verificar na implementação** — não assumir.

Cards antigos com `deck = ''` continuam exportando: coluna vazia significa deck padrão.

## Frontmatter da nota

A nota do vault ganha frontmatter antes do Markdown do Hermes:

```yaml
---
livro: Sapiens
paginas: 190-214
data: 2026-08-09
---
```

Escrito **por código**, não pelo modelo — o `titulo` vem da tabela, as páginas da sessão.
A lei de fidelidade continua valendo pro corpo: o texto do Hermes não é tocado, as citações
seguem verbatim.

O path e a mensagem de commit **não mudam** (D-E): seguem `leitura: r42` e
`Leituras/<data> - leitura-r<id>-<hash>.md`.

## Template do resumão

A tarefa criada em `terminar` leva na descrição:

```markdown
# Resumo de leitura — {titulo}

{n} sessões · páginas {min}–{max} · de {primeira_data} a {ultima_data}

## Notas da obra
{lista de links das notas no vault}

## O que eu aprendi

## O que mudou de opinião

## O que vou aplicar

## O que ficou em aberto
```

Os cabeçalhos vão vazios de propósito: quem responde é você. O sistema entrega contagem,
intervalo e ponteiros — os fatos que ele tem.

## Testes

- `books`: slug normaliza e deduplica; `POST` do mesmo título duas vezes devolve `created:false`.
- Derivadas: `pagina_atual` ignora sessão `pending` e `discarded`; obra sem sessão compilada
  devolve `pagina_atual: null` sem quebrar.
- `terminar` é idempotente: chamar duas vezes cria uma tarefa só.
- Compile com `book_id` grava `deck`; sem `book_id`, grava `''`.
- `anki.tsv()`: coluna de deck presente; card antigo com deck vazio ainda serializa 5 campos.
- Recap: falha do Hermes no recap **não** impede a gravação no vault nem os cards
  (o teste espelha o de falha do Anki que já existe).
- Sessão criada sem `book_id` segue funcionando (caminho antigo intacto).
- Frontmatter: path e mensagem de commit inalterados após a mudança (guarda da lei 7).

## Fora de escopo

Capa, ISBN, total de páginas, progresso em %, rating, "quero ler", importar do Goodreads,
busca de metadados. A estante é uma lista de o que você está lendo e onde parou. Se um dia
precisar de mais, isso vira outra spec — e provavelmente não precisa.
