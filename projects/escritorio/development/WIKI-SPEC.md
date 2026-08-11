# Wiki do sistema — tela "Como funciona" (fatia 1)

> **Origem:** item **B2** do `AETERNUM-P2-BACKLOG.md` — *"precisamos de uma página que mostra como funciona o
> app, o que são diamantes, pontos, etc"* / *"sistema inteiro, tipo um wiki"* / *"pode ser pela mesa"*
> (Leo, 09/ago/2026). Terceiro pedido: já constava na SPEC como "Manual/SOP" (§7) e no corte
> "diagramas derivados do vault → tooltips + cheatsheet estático".
>
> **Data:** 10/ago/2026. **Versão:** v3. Duas rodadas de revisão hostil (GPT-5.6 Sol xhigh) incorporadas —
> rodada 1: 15 achados, `REDESENHAR`; rodada 2: 8 achados novos, `IMPLEMENTAR COM CORREÇÕES`. Ver §13.
> **Estado:** não implementado.

---

## 1. O problema

O autor do sistema não consegue ler o próprio app. Duas evidências no mesmo dia, com o celular na mão:

- *"o que significa 'a caminho do N1'?"* e *"os diamantes apagados estão certos?"*
- *"as ideias que eu tenho, ou lembranças de tarefas? olhei pro meu quarto e lembrei de comprar cueca,
  com qual IA eu falo isso?"* — a **Captura rápida** é exatamente isso, é o fluxo principal do sistema,
  funciona há meses, e nada na tela diz o que ela é.

A segunda pergunta expõe uma confusão estrutural: **há duas IAs com contratos opostos** e o app não diz qual
serve pra quê. Captura é assíncrona e fire-and-forget; Mentor é síncrono e conversacional.

O `AETERNUM-MAPA-DO-SISTEMA.md` já existe e não resolveu — foi escrito pro leitor errado. As seções 1–6 dele
são a semente de conteúdo; as 7 e 8 (rotas, módulos) **não entram**.

### 1.1 O problema que a investigação revelou

A restrição do B2 — *nenhum número pode ser prosa* — parecia uma regra de redação. Ao verificar, é um defeito
estrutural: **tarifas e horários estão copiados em cinco lugares, nenhum autoritativo.**

| Onde | O quê | Verificado |
|---|---|---|
| `bff/app/config.py` | As tarifas | `pontos_por_rotina: 20` etc. |
| `app/src/theme.ts:73` | As tarifas, de novo | `POINTS = { tarefa:10, rotina:20, … }` — batendo por manutenção manual |
| `bff/scripts/install-cron.ps1` | Os horários que **de fato disparam** | `-At 05:30`, `-At 19:00`, … |
| `bff/app/main.py:41` | Os horários **no texto do push** | `"19h — Shutdown: fechar o trabalho, follow-ups, 3 prioridades de amanhã."` |
| `app/src/mesaView.ts:70,74` · `app/src/homeAction.ts:122,128,131` | Os horários **na tela** | `"rito das 19h"`, contador `"19h"`, `hour >= 21` |

Mude o shutdown para 18:00 e você tem: o Agendador disparando às 18h, o push dizendo 19h, a Mesa dizendo 19h e
o hero da Home só sugerindo shutdown às 19h. **A wiki seria a sexta cópia** — e a única tela cuja razão de
existir é ser confiável.

Por isso esta fatia entrega duas coisas: a tela, e a fonte única que a torna verdadeira.

## 2. Decisões travadas

| # | Decisão | Alternativas descartadas |
|---|---|---|
| D1 | **Só tela no app.** Não há manual `.md` paralelo. | Tela + doc versionado; só doc (é o que já falhou) |
| D2 | **Nome: "Como funciona"**, igual na porta, no título e no destino. | "Wiki" (promete busca); "Manual" (soa a doc que ninguém abre) |
| D3 | **Porta: ARQUIVO da Mesa** — decisão do Leo no B2. | — |
| D4 | **Índice + páginas de tópico.** | Rolagem única; só tooltips (o corte que já falhou 2×) |
| D5 | **Números vêm de `GET /wiki/parametros`.** | Reusar rotas; texto fixo |
| D6 | **Texto mora no app**, em `wikiContent.ts`, com slots. | Texto no BFF; markdown no vault |
| D7 | **Cache last-known-good validado**, com origem explícita e revalidação. | Sem cache; cache silencioso |
| D8 | **Sem diagramas nesta fatia.** | Diagramas em RN; imagens geradas no batch |
| D9 | **`bff/ritos.json` é a fonte única dos ritos**, lida por Python e por PowerShell (§3.2). | *(v1: config declara + teste parseia o `.ps1` — descartada, era duplicação disfarçada)* |
| **D10′** | **A rota alimenta o app inteiro, não só a wiki** — tarifas e horas exibidas saem de um provider único (§3.3). **Decisão do Leo em 10/ago, revertendo o D10 de v1**, depois que o custo real (7 call sites, não "4 telas") e a quinta cópia dos horários apareceram. | Só a wiki (deixa Mesa/Home/Fechar mentindo); tirar hora e preço da Mesa e da Home |
| D11 | **As janelas de antecedência do `homeAction` NÃO derivam dos ritos** (§3.3). | Derivar tudo — mudaria comportamento dentro de uma fatia de wiki |

### 2.1 A restrição dura, agora com guarda

**Nenhum número do sistema pode ser prosa.** Em v1 isso era intenção sem teste. Agora há três guardas
(§7.2–§7.4): literal proibido com blocklist de números por extenso, valores-sentinela, e inventário coberto.

§4.2 lista todo número que as páginas afirmam. **O conteúdo dirige o schema, não o contrário** — foi o erro de
v1, que montou a rota com o que por acaso já estava no `config.py`.

## 3. Arquitetura

```
bff/ritos.json ──┬─► bff/app/ritos.py ──┬─► GET /wiki/parametros ─┐
  (fonte única)  │                      ├─► NUDGE_COPY (push)     │
                 │                      └─► nudge.ps1 (ValidateSet)│
                 └─► sync-cron.ps1 (gera E reconcilia as tarefas)  │
                                                                   ▼
config.py (settings) ──────────────────────────────────► ParametrosProvider (app)
                                                                   │
                        ┌──────────────────────────────────────────┼───────────────┐
                        ▼                    ▼                     ▼               ▼
                 ComoFunciona.tsx      mesaView(ritos,points)  homeAction(ritos)  Fechar·Tasks·Capture
                        │
        wikiResolve.ts (puro: validar · decidirFonte · resolver) + wikiContent.ts (texto)
```

### 3.1 `GET /wiki/parametros`

Autenticada, **read-only**, sem estado do usuário. Saldo e nível atingido continuam em `/pontos`: esta rota
responde *"como o sistema funciona"*, não *"como você está"*.

Apesar do nome, ela **não serve só a wiki** (D10′): é a fonte dos parâmetros do app inteiro. O nome fica por
ser onde nasceu e por já descrever o conteúdo.

**Modelo de resposta é um `BaseModel` do Pydantic**, então o FastAPI valida a saída e o **JSON Schema derivado
dele é o contrato** (§3.6). Nenhum literal na rota.

```jsonc
{
  "tarifas":  { "rotina": 20, "tarefa": 10, "captura": 5,
                "fechamento": 80, "shutdown": 30, "despejo": 40 },
  "punicao":  { "limiar_furos": 3, "janela": "semana_iso",
                "desconto_padrao": 60, "teto_semanal": 200 },
  "niveis":   { "limiares": [700, 1700, 3400, 6800] },
  "ciclo":    { "semanas": 12, "inicio": "2026-07-06" },
  "staging":  { "dias_para_alerta": 3 },
  "shutdown": { "prioridades": 3 },
  "areas":    ["Trabalho", "Staging", "Corpo", "Saúde Mental", "Responsabilidade",
               "Finance", "Carreira", "Estudo", "Relacionamentos", "Lazer"],
  "ritos":    [ { "slug": "toque",      "hora": "05:30", "dia": null },
                { "slug": "checkin",    "hora": "08:20", "dia": null },
                { "slug": "jornal",     "hora": "08:30", "dia": null },
                { "slug": "digest",     "hora": "09:00", "dia": null },
                { "slug": "shutdown",   "hora": "19:00", "dia": null },
                { "slug": "fechamento", "hora": "21:00", "dia": null },
                { "slug": "review",     "hora": "20:00", "dia": "domingo" } ]
}
```

**`ritos` não traz nome nem descrição** — só slug, hora e dia. Rótulo é texto de interface e mora no app (D6).

**Ordem:** diários em ordem cronológica, semanais depois. Quem decide é o BFF.

Procedência (valores são os de 10/ago — **a rota é a verdade, não este documento**):

| Campo | Fonte |
|---|---|
| `tarifas.*` | `settings.pontos_por_rotina`, `_tarefa`, `_captura`, `_fechamento`, `_shutdown`, `_despejo` |
| `punicao.limiar_furos` | `settings.routine_miss_threshold` |
| `punicao.janela` | Constante nova em `pontos.py`. A janela **é a semana ISO** por decisão documentada no docstring do módulo, não é configurável. Rótulo, para o app dizer "na mesma semana". |
| `punicao.desconto_padrao` / `teto_semanal` | `settings.desconto_padrao` / `settings.teto_desconto_semanal` |
| `niveis.limiares` | `settings.nivel_limiares` |
| `ciclo.*` | `settings.ciclo_semanas` / `settings.ciclo_inicio` |
| `staging.dias_para_alerta` | `settings.staging_age_days` |
| `shutdown.prioridades` | Constante nova em `main.py`, hoje literal em prosa no `NUDGE_COPY` |
| `areas` | `bff/app/tasks.py:AREAS` |
| `ritos` | `bff/app/ritos.py` (§3.2) |

### 3.2 `bff/ritos.json` — a fonte única dos horários

Um arquivo, lido por Python e por PowerShell. JSON porque as duas linguagens leem nativamente (`json` /
`ConvertFrom-Json`), sem acoplar o instalador do cron ao venv.

```jsonc
[ { "slug": "toque",      "hora": "05:30", "dia": null,      "task": "Aeternum Toque",      "script": "nudge" },
  { "slug": "checkin",    "hora": "08:20", "dia": null,      "task": "Aeternum Check-in",   "script": "nudge" },
  { "slug": "jornal",     "hora": "08:30", "dia": null,      "task": "Aeternum Jornal",     "script": "nudge" },
  { "slug": "digest",     "hora": "09:00", "dia": null,      "task": "Aeternum Digest",     "script": "digest" },
  { "slug": "shutdown",   "hora": "19:00", "dia": null,      "task": "Aeternum Shutdown",   "script": "nudge" },
  { "slug": "fechamento", "hora": "21:00", "dia": null,      "task": "Aeternum Fechamento", "script": "nudge" },
  { "slug": "review",     "hora": "20:00", "dia": "domingo", "task": "Aeternum Review",     "script": "nudge" } ]
```

`script` substitui o booleano `nudge` de v2: diz **qual** script roda (`nudge.ps1` ou `run-digest.ps1`), o que
o gerador precisa saber e um booleano não expressava.

Cinco consumidores, nenhuma cópia:

- **`bff/app/ritos.py`** — carrega e valida no import: `slug` único, **`task` único** (dois ritos com a mesma
  task fariam o segundo `Register-ScheduledTask -Force` sobrescrever o primeiro em silêncio), `hora` no
  formato `HH:MM`, `dia ∈ {null} ∪ dias da semana`, `script ∈ {nudge, digest}`. Expõe `RITOS`, `hora(slug)`,
  `hora_curta(slug)` (`"19h"`, `"5h30"`).
- **`NUDGE_COPY`** — as horas saem do texto e viram interpolação. O tom seco da lei 4 fica igual; só o número
  passa a ser lido.
- **`nudge.ps1`** — hoje tem `[ValidateSet("toque","checkin","jornal","shutdown","closing","review")]` na
  linha 1. **É por aqui que a renomeação de v2 quebraria o rito das 21h**: o instalador passaria
  `-Kind fechamento` e o script morreria no ValidateSet, antes de qualquer chamada HTTP — o nudge do
  fechamento sumiria em silêncio. O `ValidateSet` entra na migração e um teste exige que seus membros sejam
  exatamente os slugs com `script: "nudge"`.
- **`sync-cron.ps1`** (extraído do `install-cron.ps1`) — gera os `Register-ScheduledTask` do JSON:
  `dia: null` → `-Daily`, `dia: "domingo"` → `-Weekly -DaysOfWeek Sunday`. Nenhum `-At` literal.
- **`GET /wiki/parametros`** — projeta slug/hora/dia.

**Renomeação `closing` → `fechamento`:** um único vocabulário, aplicado em `NUDGE_COPY`, `nudge.ps1` e no nome
da task. A lição do B3 (Ritmos × Rotinas) antes de doer.

#### Reconciliação do estado instalado

Gerar do JSON conserta as cópias em código; **não conserta o Agendador do Windows**, que guarda o estado
instalado. Em v2 eu declarei isso como risco residual aceito; o revisor chamou de racionalização e tem razão:
o BFF roda na mesma máquina Windows, então há como reconciliar. Duas medidas:

1. **`sync-cron.ps1` reconcilia, não só registra.** Compara o conjunto desejado (as `task` do JSON) com
   `Get-ScheduledTask "Aeternum *"` e **remove as obsoletas** — rito renomeado ou apagado deixaria a task
   antiga instalada e disparando em paralelo. `Aeternum BFF` é preservada explicitamente (não vem do JSON).
2. **`start-bff.ps1` chama `sync-cron.ps1` no boot.** Como o BFF já sobe no logon, o estado instalado converge
   sozinho: mudar o `ritos.json` e reiniciar basta. Reinstalar deixa de ser um passo manual que dá pra
   esquecer.

**Testável:** `sync-cron.ps1` expõe um modo `-DryRun` que **devolve o plano** (lista de task, gatilho, script)
sem registrar nada. Sem isso, caminho errado do JSON, tradução errada de `domingo` ou escolha errada entre
`nudge.ps1` e `run-digest.ps1` passariam com toda a suíte verde (§7.9).

### 3.3 `ParametrosProvider` — o provider do app (D10′)

A rota vira fonte única também para o app. Hidrata uma vez, com os valores de hoje como ponto de partida.

- **Valor inicial** = a tabela que hoje está em `theme.ts:POINTS` + as horas de hoje. Nada pisca e nada quebra
  se a rede falhar: o app parte do que já mostrava.
- **Encaixa no padrão que já existe.** `mesaView.montarMesa` e `closingPoints` **já recebem** a tabela por
  parâmetro, com o comentário *"a tabela de pontos entra por parâmetro; o teste é quem importa o POINTS de
  produção"*. A mudança é passar também `ritos` e trocar a origem — não é arquitetura nova, é usar a que está
  lá.
- **Call sites:** 7 de `POINTS.` (`Capture.tsx:1698`, `Fechar.tsx:360,369,418`, `Tasks.tsx:72,107,416`) e 3 de
  hora (`mesaView.ts:70,74`, `homeAction.ts:131`).
- **`theme.ts:POINTS`** deixa de ser lido pelas telas e passa a ser o **valor de partida do provider**, com
  comentário dizendo isso. Não é apagado: é o fallback honesto de primeira abertura.

#### D11 — o que NÃO deriva, e por quê

`homeAction.actionForAt` usa hora como **fluxo de controle**, não só como texto:

| Linha | Condição | Deriva? |
|---|---|---|
| 116 | `hour < 8 && !template` | **Não.** Janela da abertura, não o horário do toque (05:30) |
| 119 | `hour < 12 && !checkin.feito` | **Não.** Janela do check-in, não o horário dele (08:20) |
| 122 | `reading > 0 && hour < 19` | **Sim** → `ritos.shutdown.hora` |
| 125 | `sunday && hour >= 17` | **Não.** Antecedência de 3h para o review das 20h |
| 128 | `hour >= 19 && hour < 21` | **Sim** → `shutdown` e `fechamento` |
| 131 | `hour >= 21` | **Sim** → `ritos.fechamento.hora` |

Os três que derivam são o horário do rito. Os outros três são janelas escolhidas, e convertê-los mecanicamente
mudaria comportamento e quebraria os testes que fixam a lógica atual (`homeAction.test.mjs`) — mudança de
comportamento contrabandeada dentro de uma fatia de wiki. Ficam como estão, com comentário no código dizendo
que são janelas, não horários.

`actionForAt` ganha um parâmetro `ritos` no mesmo estilo de `montarMesa(sinais, points)`; os testes existentes
passam a tabela explicitamente.

### 3.4 `app/src/wikiContent.ts` — o texto

Dado puro, sem JSX e **sem import de valor** — mesmo padrão do `mesaView.ts`, para o teste `.mjs` importar sem
resolver caminho relativo em runtime.

```ts
export type Bloco =
  | { tipo: "p" | "passo" | "nota"; texto: string }
  | { tipo: "lista-areas" }
  | { tipo: "lista-ritos" };

export type RitoTexto = { nome: string; pede: string; grava: string };

export type Pagina = { slug: string; titulo: string; resumo: string; blocos: Bloco[] };

export const PAGINAS: Pagina[] = [ /* … */ ];
export const RITOS_TEXTO: Record<string, RitoTexto> = { /* … por slug */ };
```

**`RITOS_TEXTO` é obrigatório para todo slug do contrato atual** — um teste exige `nome`, `pede` e `grava` não
vazios para cada slug do `ritos.json`. O fallback (hora + slug, sem descrição) existe **só para skew de
versão**: um BFF mais novo mandando um rito que o app ainda não conhece. Em v2 o fallback era permissivo e
contradizia a pergunta de aceite `g` ("o que cada rito pede") — rito novo apareceria mudo e o aceite passaria.

Números entram como slots: `"Cada rotina marcada vale +{tarifas.rotina}."`

### 3.5 `app/src/wikiResolve.ts` — o módulo puro

Em v1 a resolução morava dentro do componente e nenhum teste a exercitava. Extraída, no padrão de
`mesaView.ts` / `closingPoints.ts`. Não há teste de render de React Native neste projeto e esta fatia não vai
introduzir um — por isso **a decisão de qual fonte usar também é pura**, e não estado de componente.

```ts
export type Params = { /* espelha o schema */ };

export type Fonte =
  | { tipo: "fresco";       params: Params }
  | { tipo: "cache";        params: Params; salvoEm: string }   // ISO-8601
  | { tipo: "indisponivel"; motivo: "sem-cache" | "sessao" | "rede" };

export type Entrada = {
  resposta: { ok: true; corpo: unknown } | { ok: false; status: number | null };
  cache: unknown;                                   // o que veio do storage, cru
};

export function validar(bruto: unknown): Params | null;   // null se o formato não bate
export function decidirFonte(e: Entrada): Fonte;          // toda a política de §6, pura
export function resolver(texto: string, f: Fonte): string;
export function paginaPronta(p: Pagina, f: Fonte): BlocoPronto[];
```

`Fonte` é **união discriminada**. Em v2 era `{params, idade: string|null}`, e `idade: null` significava tanto
"resposta fresca" quanto "cache sem timestamp" — a tela não tinha como distinguir e podia apresentar cache
como fresco. Agora `cache` **exige** `salvoEm`; envelope de cache sem timestamp não valida e é descartado.

`validar` é a mesma função que guarda a escrita e a leitura do cache. Payload que não valida nunca entra no
cache e nunca substitui um bom.

`decidirFonte` concentra o que sobraria no componente: 200-válido, 200-inválido, 401, erro de rede, sem cache,
cache corrompido. O que fica no `.tsx` é wiring — buscar, chamar, desenhar.

### 3.6 O contrato: schema derivado, não fixture artesanal

Em v2 o contrato era um exemplo de resposta commitado e uma comparação de **caminhos**. Duas falhas reais: não
via tipo (o BFF podia trocar `hora: "05:30"` por `hora: 530` e passar), e um array vazio não produzia caminho
nenhum, contradizendo a igualdade exata com um fixture não vazio.

O FastAPI já gera JSON Schema do modelo Pydantic. **O schema é o contrato:**

- `app/tests/fixtures/wiki-schema.json` — o JSON Schema do modelo, commitado.
- Teste do BFF (§7.7) **regenera** do modelo e exige igualdade com o arquivo commitado. Mudou o modelo sem
  atualizar o contrato → quebra.
- Teste do app (§7.2, §7.4) valida slots **e tipos** contra o schema, e `validar()` é escrito contra ele.
- `app/tests/fixtures/wiki-parametros.json` continua existindo, mas só como **massa de teste** — não é mais o
  contrato.

Caminho de array é `areas[]` / `ritos[].hora`: o schema descreve a forma do elemento, e cardinalidade fica de
fora. Array vazio é válido, e a tela renderiza lista vazia com nota.

## 4. Conteúdo

### 4.1 As nove páginas

| Slug | Título | O que ela mata |
|---|---|---|
| `comece` | Comece por aqui | O que é o app em 30s: as três camadas, as três leis, e um mapa "quero X → vou em Y" |
| `captura` | Captura rápida | *"lembrei de comprar cueca, com qual IA falo isso?"* — é aqui, é um toque, o worker classifica depois |
| `duas-ias` | As duas IAs | O contrato oposto: Captura assíncrona e fire-and-forget × Mentor síncrono e conversacional, com exemplos lado a lado |
| `pontos` | Diamantes e pontos | *"o que significa 'a caminho do N1'"*, *"os diamantes apagados estão certos?"* — o que paga, quanto, o que desconta, nível é vitalício, e o ciclo |
| `ritos` | Ritos do dia | O loop diário: que rito, que hora, o que pede, **o que grava** |
| `tarefas` | Tarefas e Triagem | Por que toda tarefa nasce em Staging e por que mover é ato seu (lei 3); o envelhecimento do Staging; as áreas |
| `leitura` | Leitura | A sessão: hooks por voz, compilar não publica, o portão do preview, de onde saem os cartões Anki |
| `guarda` | Onde tudo é salvo | Vault × SQLite × ClickUp × celular; e as integrações de saída — o que sobrevive se cada peça cair |
| `salas` | As outras salas | Edificação, Melhorias, Reduzir e Agenda — as quatro superfícies do ARQUIVO que nenhuma outra página explicava |

**Diamante = nível.** Confirmado em `Revisao.tsx:68`: quatro losangos; os acesos são os níveis já batidos, os
apagados os que faltam. "A caminho do N1" vem de `proximo_nivel.faltam` (`api.ts:369`). A página `pontos` diz
isso com essas palavras.

O **ciclo** mora em `pontos`: 12 semanas só faz sentido junto do que ele mede.

#### Matriz de cobertura

O B2 pede *"o sistema inteiro"*. **Todo destino da Mesa e toda integração de saída aponta para a página que o
explica.** Item sem página é achado, não detalhe.

| Superfície | Página |
|---|---|
| Capturar (captura rápida) | `captura` |
| Capturar (leitura) · Anki | `leitura` |
| Mentor / Chat | `duas-ias` |
| Tarefas · Triagem · Staging · as 10 áreas | `tarefas` |
| Abertura · Shutdown · Fechar · Review · Digest · Toque · Jornal | `ritos` |
| Ritmos (rotinas) · pontos · níveis · punição · ciclo | `pontos` |
| Edificação · Melhorias · Reduzir · Agenda | `salas` |
| Vault · SQLite · ClickUp · fila offline do celular | `guarda` |
| Hermes · Expo Push · Telegram · GCal · Outlook/ICS | `guarda` |
| Ajustes | *(sem página — é configuração, não conceito)* |

#### Regras de conteúdo

- **Tom:** segunda pessoa, presente, frase curta. *"Você joga a ideia fora da cabeça e segue. O worker
  classifica depois."* Nunca *"o sistema permite ao usuário registrar"*.
- **Tamanho:** teto de ~180 palavras por página. Página que não cabe virou duas.
- **Listas vivas:** `areas` e `ritos` são blocos renderizados da resposta, nunca escritos à mão.
- **Fora:** rotas do BFF, nomes de arquivo, nomes de módulo.
- **Obrigatório e verbatim:** a página `captura` traz o exemplo *"lembrei de comprar cueca"* com a resposta
  explícita — vai para a Captura; o recibo é imediato, a classificação vem depois. Foi a pergunta que provou o
  buraco; a wiki que não a responde com essas palavras não entregou.

### 4.2 Inventário de números

**Contrato entre conteúdo e rota** — número que uma página precisa e não está aqui é bug de spec, não decisão
do implementador.

| Número | Slot | Página |
|---|---|---|
| Tarifa de rotina, tarefa, captura, fechamento, shutdown, despejo | `tarifas.*` | `pontos`, `ritos`, `captura` |
| Limiar de furos | `punicao.limiar_furos` | `pontos` |
| Janela do padrão | `punicao.janela` → rótulo "na mesma semana" | `pontos` |
| Desconto por padrão · teto semanal | `punicao.desconto_padrao` · `punicao.teto_semanal` | `pontos` |
| Limiares de nível | `niveis.limiares` | `pontos` |
| Semanas do ciclo · início | `ciclo.semanas` · `ciclo.inicio` | `pontos` |
| Dias até o Staging alertar | `staging.dias_para_alerta` | `tarefas` |
| Prioridades do Shutdown | `shutdown.prioridades` | `ritos` |
| Hora e dia de cada rito | `ritos[].hora`, `ritos[].dia` | `ritos` |
| As 10 áreas | `areas[]` | `tarefas` |

#### Literais permitidos

Em v2 a allowlist era uma lista de dígitos soltos (`2`, `3`, `4`) e tinha dois furos que a rodada 2 pegou:
liberava esses dígitos em **qualquer** uso, e **impedia escrever "N1"** — a frase que a página `pontos`
é obrigada a explicar.

Regra nova, em três categorias:

1. **Tokens de nível `N1`…`Nn`** — estruturais, permitidos, mas o teste exige que `n` esteja dentro da
   quantidade de níveis do contrato (`niveis.limiares`). Escrever `N7` com quatro limiares quebra. Ao dizer
   *quantos* níveis existem ou *quanto falta*, usa-se slot, nunca literal.
2. **Contagens estruturais fixas** — "as três camadas", "as três leis", "as duas IAs". Permitidas **por
   frase**, casadas contra uma lista curta de expressões exatas; não é o dígito solto que libera.
3. **Todo o resto é proibido**, inclusive **por extenso**: uma blocklist de numerais escritos (`vinte`,
   `oitenta`, `doze`, …) impede fugir do teste trocando `20` por "vinte" — o furo que a rodada 2 apontou.

## 5. Navegação e portas de entrada

**Porta principal — ARQUIVO da Mesa.** Item novo em `mesaView.ts`, **incondicional**, **último do grupo, depois
de `Ajustes`** — é referência, não trabalho parado:

```
item("comofunciona", "Como funciona", "o sistema explicado")
```

**Portas contextuais** — as duas dúvidas nasceram nestas telas:

| Origem | Abre |
|---|---|
| Bloco de nível da Home (`Home.tsx:146`) | página `pontos` |
| Tela Capturar, junto do campo de captura rápida | página `captura` |

`openDestination` (`App.tsx:164`) aceita `comofunciona` com slug de página opcional.

**Renomeações:** nenhuma no app. Fora dele, `closing` → `fechamento` em `NUDGE_COPY`, `nudge.ps1` e no nome da
task (§3.2).

## 6. Falhas e cache

Toda esta política vive em `decidirFonte()` (§3.5) e é testada como função pura.

| Situação | `Fonte` | O que a tela mostra |
|---|---|---|
| 200 e valida | `fresco` | Números, sem selo. Cache substituído. |
| 200 e **não** valida | `cache` ou `indisponivel` | Tratada como falha. **O cache bom NÃO é tocado.** |
| Falha de rede, com cache | `cache` | Números + selo `valores de 10/ago/2026` |
| Falha de rede, sem cache | `indisponivel: "rede"` | Slots viram `—`, aviso e botão `tentar de novo` |
| 401, com cache | `cache` | Cache + nota "sessão expirada — entre em Ajustes para atualizar os valores" |
| 401, sem cache | `indisponivel: "sessao"` | `—` + a mesma nota. **A wiki nunca expulsa para o login** — é tela de referência, e expulsar quem só quer ler é hostil |
| Cache corrompido ou sem `salvoEm` | descartado | Cai no caso "sem cache" |
| Lista vazia (`areas: []`) | qualquer | Bloco com nota "não consegui ler a lista", não erro |

**O texto nunca falha** — mora no bundle. A wiki abre sempre; o que pode faltar são os números, e quando faltam
ela diz.

**Cache — last-known-good validado.** Três regras:

1. **Só grava depois de `validar()` passar.** Um 200 parcial num rollout incompatível não pode sobrescrever um
   cache completo.
2. **Não expira.** Expirar deixaria o Leo sem números justamente offline. Quem carrega a honestidade é a
   origem explícita (`Fonte.tipo`) e o selo com **dia, mês e ano**.
3. **Revalida ao ganhar foco**, não só ao montar, mais o botão `tentar de novo`.

## 7. Testes

Dez. Os cinco primeiros são o que faz o aceite ser verdade em vez de promessa.

| # | Arquivo | O que prova |
|---|---|---|
| 1 | `app/tests/wikiContent.test.mjs` | **Slot órfão** — todo `{...}` existe no schema (§3.6), com o tipo certo |
| 2 | idem | **Literal proibido** — dígito fora de slot que não caia nas três categorias de §4.2 quebra; inclui a blocklist de numerais por extenso |
| 3 | idem | **Valores-sentinela** — renderiza todas as páginas com um `Params` em que cada número é um sentinela distinto, e falha se qualquer valor de produção aparecer no texto. Pega o número copiado à mão que casualmente bate com o real |
| 4 | idem | **Inventário coberto** — todo slot de §4.2 é usado por alguma página; e todo slug de `ritos.json` tem `RITOS_TEXTO` com `nome`/`pede`/`grava` não vazios |
| 5 | `app/tests/wikiResolve.test.mjs` | **`decidirFonte`** nos oito casos da tabela de §6; **`validar`** com payload completo, parcial, tipo errado, array vazio, `null` e cache sem `salvoEm`; **`resolver`** com slot presente, ausente e malformado; fallback de rito desconhecido. Nenhum caminho devolve `undefined` |
| 6 | `bff/tests/test_ritos.py` | `ritos.json` carrega e valida: `slug` único, **`task` único**, `hora` `HH:MM`, `dia` válido, `script ∈ {nudge,digest}`; o `ValidateSet` do `nudge.ps1` é exatamente os slugs com `script: "nudge"`; e **nenhum texto do `NUDGE_COPY` contém hora escrita à mão** |
| 7 | `bff/tests/test_wiki_parametros.py` | 401 sem token; cada valor vem de `settings`/`ritos.py` (muda o setting → muda a resposta); e o JSON Schema regenerado do modelo é idêntico ao commitado |
| 8 | `app/tests/mesaView.test.mjs` | `comofunciona` em `TODOS_OS_DESTINOS` (11 → 12) e nas três asserções de ordem; e a hora exibida vem do parâmetro `ritos`, não de literal |
| 9 | `bff/tests/test_sync_cron.py` | O plano do `sync-cron.ps1 -DryRun` bate com o `ritos.json`: sete tasks, gatilho certo (`-Daily` × `-Weekly -DaysOfWeek Sunday`), script certo; e uma task `Aeternum *` que não está no JSON aparece na lista de remoção, enquanto `Aeternum BFF` não |
| 10 | `app/tests/homeAction.test.mjs` | Os três limiares que derivam (§3.3) mudam quando a tabela `ritos` muda; as três janelas de antecedência **não** mudam |

**Correção ao que o B2 diz:** o backlog avisa que isto "muda a contagem de 11 destinos e o teste de 2160
combinações". As 2160 (`mesaView.test.mjs:86`) são `5 × 4 × 3 × 3 × 3 × 4`, o produto das **combinações de
sinais** — não têm relação com quantos destinos existem, e **continuam 2160**.

**O que nenhum teste cobre, e é honesto dizer:**

- **Se o texto está bom.** Nenhuma suíte prova que uma frase esclarece. Por isso o aceite (§10) é uma lista de
  perguntas concretas respondidas pelo Leo.
- **A composição do `.tsx`.** `decidirFonte` tira a política do componente, mas o wiring (buscar, navegar por
  slug, desenhar) fica sem teste automatizado — este projeto não tem infraestrutura de render de RN, e criar
  uma é fatia própria. Coberto pelo aceite manual §10.4.

## 8. Arquivos tocados

**Novos**

- `bff/ritos.json` · `bff/app/ritos.py` · `bff/scripts/sync-cron.ps1`
- `bff/tests/test_ritos.py` · `bff/tests/test_wiki_parametros.py` · `bff/tests/test_sync_cron.py`
- `app/src/wikiContent.ts` · `app/src/wikiResolve.ts` · `app/src/screens/ComoFunciona.tsx`
- `app/src/parametros.tsx` (o provider)
- `app/tests/wikiContent.test.mjs` · `app/tests/wikiResolve.test.mjs`
- `app/tests/fixtures/wiki-schema.json` · `app/tests/fixtures/wiki-parametros.json`

**Alterados**

- `bff/app/main.py` — rota nova; `NUDGE_COPY` interpola hora e nº de prioridades; `closing` → `fechamento`
- `bff/scripts/install-cron.ps1` — passa a chamar `sync-cron.ps1`
- `bff/scripts/nudge.ps1` — `ValidateSet` com o vocabulário novo
- `bff/scripts/start-bff.ps1` — chama `sync-cron.ps1` no boot
- `bff/app/pontos.py` — expõe a constante da janela (`semana_iso`)
- `app/src/api.ts` — tipo + fetch
- `app/src/theme.ts` — `POINTS` vira valor de partida do provider, com comentário
- `app/src/mesaView.ts` · `app/src/homeAction.ts` — parâmetro `ritos`; hora deixa de ser literal
- `app/src/screens/Capture.tsx` · `Fechar.tsx` · `Tasks.tsx` — 7 call sites de `POINTS.` passam pelo provider
- `app/src/screens/Home.tsx` — provider + porta contextual
- `app/App.tsx` — `Tab`, `TITLES`, `openDestination`, render, provider no topo
- `app/tests/mesaView.test.mjs` · `app/tests/homeAction.test.mjs`

## 9. Fora de escopo

- **Diagramas** (D8) — fatia 2.
- **Busca dentro da wiki** — nove páginas cabem num índice.
- **Testes de render de React Native** — infraestrutura que o projeto não tem; fatia própria.
- **Derivar as janelas de antecedência do `homeAction`** (D11) — seria mudança de comportamento.
- Qualquer mudança no pipeline de captura, na economia ou em `/pontos`. A rota nova é read-only.

## 10. Critério de aceite

**1. As perguntas.** Com o app na mão e sem perguntar a ninguém, o Leo responde:

| # | Pergunta | Onde |
|---|---|---|
| a | O que é um diamante? | `pontos` |
| b | O que significa "a caminho do N1"? | `pontos` |
| c | Os diamantes apagados estão certos? | `pontos` |
| d | O que paga ponto, e quanto cada coisa paga? | `pontos` |
| e | O que desconta ponto, quando, e qual o teto? | `pontos` |
| f | O que é o ciclo e quando ele começou? | `pontos` |
| g | Que ritos existem, a que horas, o que cada um pede **e o que cada um grava**? | `ritos` |
| h | *"Lembrei de comprar cueca"* — falo com qual IA? | `captura` |
| i | Qual a diferença entre a Captura e o Mentor? | `duas-ias` |
| j | Por que minha tarefa foi parar em Staging? | `tarefas` |
| k | Se eu perder o celular, o que sobrevive? | `guarda` |
| l | Compilar a leitura já publica no vault? | `leitura` |
| m | Melhoria e tarefa são a mesma coisa? Melhoria cobra atraso? | `salas` |
| n | Que sistemas de fora o Aeternum toca, e o que ele manda pra cada um? | `guarda` |

**2. Fonte única, verificada de ponta a ponta.** Mudar `pontos_por_rotina` na config muda **a wiki, a Mesa, o
Fechar e as Tarefas** — sem editar tela nenhuma. Mudar a hora no `ritos.json` e reiniciar muda **a wiki, o
gatilho do Agendador, o texto do push, a Mesa e o hero da Home**.

**3. Portas.** Tocar no bloco de nível da Home abre `pontos`; tocar na dica da Capturar abre `captura`.

**4. Degradação.** BFF desligado e sem cache: a wiki abre, o texto aparece inteiro, os números viram `—` com
aviso e retry. Com cache: aparecem com selo de data completa. Com sessão expirada: a wiki **não** expulsa.

**5. O nudge não quebrou.** Depois da renomeação `closing` → `fechamento`, o nudge das 21h chega. Drill
manual — este é o caminho que a v2 teria quebrado em silêncio.

**6. Suíte.** `python -m pytest -q` e os testes `.mjs` passam, incluindo os dez de §7.

## 11. Complexidade

A rodada 1 recomendou cortar de nove páginas para quatro. Recusei, e a rodada 2 aceitou o argumento como
**sólido**: a infraestrutura é custo fixo, as cinco páginas extras são custo marginal, e este é o terceiro
pedido da mesma coisa — as duas primeiras vezes morreram por corte. Ressalva do revisor, justa: cada página
não custa "uma linha"; conteúdo e aceite dão trabalho real. Está refletido nas perguntas `l`, `m` e `n`.

O que a rodada 2 apontou como excesso era o **contrato artesanal** (Pydantic + validador TS + fixture manual +
comparação de caminhos, que ainda assim não garantia tipo). Aceito: §3.6 troca isso por schema derivado. É a
única parte da v3 que ficou **mais simples** que a v2.

O crescimento restante — provider, `sync-cron.ps1`, reconciliação, dez testes — não é ornamento: é o preço de
a wiki não ser a sexta cópia. O revisor recomendou exatamente isso no veredito de complexidade da rodada 2.

## 12. Ordem de implementação

Três blocos, cada um verificável sozinho. O primeiro não tem tela nenhuma e já paga por si.

1. **Fonte única no servidor** — `ritos.json`, `ritos.py`, `sync-cron.ps1` com reconciliação e `-DryRun`,
   `NUDGE_COPY` interpolado, `nudge.ps1` renomeado, `start-bff.ps1` chamando o sync. Testes 6 e 9.
   **Verificação:** mudar uma hora no JSON, reiniciar, e ver o Agendador e o push mudarem juntos.
2. **Rota e provider** — `GET /wiki/parametros`, schema commitado, `ParametrosProvider`, os 7 call sites de
   `POINTS.` e os 3 de hora. Testes 7, 8 e 10. **Verificação:** mudar `pontos_por_rotina` e ver Mesa, Fechar e
   Tarefas mudarem.
3. **A tela** — `wikiContent.ts`, `wikiResolve.ts`, `ComoFunciona.tsx`, portas, item da Mesa. Testes 1–5.
   **Verificação:** as 14 perguntas de §10.

## 13. Histórico de revisão

**v1 → v2** — rodada 1 (15 achados, `REDESENHAR`): teste de literal com allowlist; aceite virou lista de
perguntas; inventário de números dirigindo o schema; matriz de cobertura e página `salas`; Pydantic +
`validar()`; caminhos de array normalizados; blocos de lista com fallback; `wikiResolve.ts` extraído e testado;
cache só grava depois de validar; `ritos` sem texto de UI; revalidação por foco; 401 explícito. E o desenho de
D9 caiu por um achado próprio: os horários estavam também no `NUDGE_COPY`.

**v2 → v3** — rodada 2 (8 resolvidos, 6 parciais, 1 não resolvido; 8 achados novos; veredito subiu para
`IMPLEMENTAR COM CORREÇÕES`):

| Achado da rodada 2 | Resposta |
|---|---|
| CRÍTICO — `ritos.json` não era fonte única: Mesa e Home têm hora hardcoded | Confirmado no código (`mesaView.ts:70,74`, `homeAction.ts:131`). Provider (§3.3) — **decisão do Leo, D10′** |
| CRÍTICO — renomear `closing` quebraria o `nudge.ps1` | Confirmado: `ValidateSet` na linha 1 mataria o rito das 21h antes do HTTP. `nudge.ps1` entra na migração + teste 6 |
| ALTO — instalador não reconcilia task removida/renomeada | `sync-cron.ps1` compara e remove obsoletas, preservando `Aeternum BFF` (§3.2) |
| ALTO — consumidor PowerShell sem teste | Modo `-DryRun` devolvendo o plano + teste 9 |
| ALTO — allowlist impedia escrever "N1" | Regra em três categorias; tokens `N1…Nn` validados contra `niveis.limiares` (§4.2) |
| ALTO — `Fonte` podia mostrar cache como fresco | União discriminada `fresco \| cache \| indisponivel`, `salvoEm` obrigatório (§3.5) |
| ALTO — `task` sem unicidade validada | Validado no import do `ritos.py` + teste 6 |
| MÉDIO — fallback de rito contradizia a completude | `RITOS_TEXTO` obrigatório para todo slug do contrato; fallback só para skew de versão (§3.4) |
| PARCIAL 1 — literal por extenso e dígitos liberados globalmente | Blocklist de numerais escritos + contagens casadas por frase + teste de sentinela (§4.2, teste 3) |
| PARCIAL 3 — arquivo não é agenda instalada | Aceito como racionalização minha. `start-bff.ps1` roda o sync no boot: o estado converge sozinho (§3.2) |
| PARCIAL 6 — aceite passava com `leitura`/`salas`/integrações fracas | Perguntas `l`, `m`, `n` e "o que cada rito grava" na `g` (§10) |
| PARCIAL 7 e 8 — contrato só comparava caminhos; array vazio contradizia | Schema derivado do Pydantic vira o contrato; fixture vira massa de teste (§3.6) |
| PARCIAL 11 — cache/401/foco sem teste | `decidirFonte` puro cobre a política inteira (teste 5); o que resta sem teste está declarado em §7 |
| §11 julgado SÓLIDO | Mantido, com a ressalva sobre custo de conteúdo incorporada |

## 14. Fatias seguintes

| Fatia | O quê | Por que depois |
|---|---|---|
| 2 | Diagramas dos fluxos principais | Custo de layout real; o aceite não pede diagrama |
| 3 | Infraestrutura de teste de render de RN | Fecharia o buraco declarado em §7; vale para o app todo, não só a wiki |
| 4 | Links "o que é isso?" nas demais telas | Aditivo; só faz sentido com a fatia 1 no ar |
