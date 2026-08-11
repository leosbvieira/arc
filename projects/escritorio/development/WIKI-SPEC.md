# Wiki do sistema — tela "Como funciona" (fatia 1)

> **Origem:** item **B2** do `AETERNUM-P2-BACKLOG.md` — *"precisamos de uma página que mostra como funciona o
> app, o que são diamantes, pontos, etc"* / *"sistema inteiro, tipo um wiki"* / *"pode ser pela mesa"*
> (Leo, 09/ago/2026). Terceiro pedido: já constava na SPEC como "Manual/SOP" (§7) e no corte
> "diagramas derivados do vault → tooltips + cheatsheet estático".
>
> **Data:** 11/ago/2026. **Versão:** v6. Cinco rodadas de revisão hostil (GPT-5.6 Sol xhigh) incorporadas —
> r1: 15 achados, `REDESENHAR`; r2: 8 novos; r3: 9, **nenhum crítico**; r4: 6, nenhum crítico; r5: 3, nenhum
> crítico, **mas 2 regressões introduzidas pela v5**. Ver §13. **Estado:** não implementado.
>
> **Entrega em duas fatias** (§12): **1A** é a fonte única e fecha sozinha; **1B** é a tela e depende dela.

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
     wikiResolve.ts (puro: validar · decidir · resolver) · wikiNav.ts · wikiContent.ts (texto)
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
                { "slug": "closing",    "hora": "21:00", "dia": null },
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
  { "slug": "closing",    "hora": "21:00", "dia": null,      "task": "Aeternum Fechamento", "script": "nudge" },
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
- **`nudge.ps1`** — tem `[ValidateSet("toque","checkin","jornal","shutdown","closing","review")]` na linha 1.
  **Não muda** (ver a nota de slug abaixo), mas um teste passa a exigir que seus membros sejam exatamente os
  slugs com `script: "nudge"` — se um rito for adicionado ao JSON sem entrar no ValidateSet, o gatilho novo
  morreria antes de qualquer chamada HTTP.
- **`sync-cron.ps1`** (extraído do `install-cron.ps1`) — gera os `Register-ScheduledTask` do JSON:
  `dia: null` → `-Daily`, `dia: "domingo"` → `-Weekly -DaysOfWeek Sunday`. Nenhum `-At` literal.
- **`GET /wiki/parametros`** — projeta slug/hora/dia.

**Nota de slug: o rito das 21h continua `closing`, e isto é uma correção da v6.** Até a v5 a spec mandava
renomear para `fechamento` "por um único vocabulário". Ao planejar a implementação eu fui ver os consumidores:
`closing` é o vocabulário **estabelecido do BFF** — `/closing/routines`, `/closing/draft`, `/closing/approve`,
o evento `closing_approved` (`main.py:2833`), o kind de notificação `nudge_closing` (`notify.py:148`) e o
`Literal` de `main.py:483`. Renomear só o nudge não unificaria nada: criaria um racha novo entre as rotas e o
gatilho, e faria as linhas de `notif_log` pararem de casar com o histórico.

A lição do B3 (Ritmos × Rotinas) era sobre **palavras que o Leo vê** — três superfícies, duas palavras, ele
procurou "Rotinas" e não achou. `closing` nunca aparece na tela: o que ele lê é "Fechar o dia". Slug interno em
inglês e rótulo em português não é o defeito do B3.

**O que isso cancela:** a migração inteira do achado CRÍTICO da rodada 2 (o `ValidateSet` que mataria o rito das
21h). O risco some porque a mudança some — só fica o teste que vigia a igualdade. O nome da task do Windows
(`Aeternum Fechamento`) continua como está, porque é rótulo, não slug.

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

### 3.3 `ParametrosProvider` — a autoridade única do app (D10′)

**O provider é o único dono de buscar, validar, gravar cache e revalidar.** Nenhuma tela — nem a wiki — faz
fetch por conta própria. Em v3 o provider "hidratava" e o `ComoFunciona.tsx` também buscava e revalidava por
foco: dois donos, e a wiki podia receber valor novo enquanto a Mesa continuava no anterior. Agora há um dono.

```ts
export function useParametros(): Fonte;      // §3.5
export function useRevalidar(): () => void;  // o botão "tentar de novo" e o refresh por foco
```

- **Encaixa no padrão que já existe.** `mesaView.montarMesa` e `closingPoints` **já recebem** a tabela por
  parâmetro, com o comentário *"a tabela de pontos entra por parâmetro; o teste é quem importa o POINTS de
  produção"*. A mudança é passar também `ritos` e trocar a origem — não é arquitetura nova, é usar a que está lá.
- **Call sites:** 7 de `POINTS.` (`Capture.tsx:1698`, `Fechar.tsx:360,369,418`, `Tasks.tsx:72,107,416`) e 3 de
  hora (`mesaView.ts:70,74`, `homeAction.ts:131`).
- **Guarda de migração** (teste 11): nenhum arquivo fora de `theme.ts` e `parametros.tsx` pode importar
  `POINTS`. Sem isso, `Capture.tsx` podia continuar lendo `POINTS.despejoBonus` e o aceite baseado em
  `pontos_por_rotina` passaria mesmo assim.

#### O bootstrap tem procedência

Eu escrevi em v3 que `theme.ts:POINTS` seria o "valor de partida honesto". Não é honesto se não se identifica:
numa primeira abertura sem rede, o app mostraria as tarifas e horas embutidas **sem selo**, indistinguíveis do
valor real do servidor — a segunda fonte silenciosa que esta fatia existe para matar.

Correção em três partes, todas cobradas pela rodada 4:

**1. `DEFAULT_PARAMS` é completo e validado.** Em v4 eu criei a variante `padrao` sem nada capaz de produzi-la:
`POINTS` sozinho não é um `Params` — falta ritos, níveis, ciclo, staging, áreas. Agora existe um
`DEFAULT_PARAMS` **inteiro**, no bundle, e o teste 8 o valida contra o mesmo schema da rota. Ele não pode
divergir de forma; só de valor, que é o ponto.

**2. A recusa é código, não convenção.** Um seletor puro, testado:

```ts
export function fonteParaWiki(f: Fonte): Fonte;   // padrao → indisponivel: "sem-cache"
```

Em v4 a política era *"quem quiser recusar recusa no `switch`"* — um `switch` esquecido mostraria embutido na
wiki e tudo passaria. Agora a wiki lê a fonte **só** por este seletor, e o teste 14 prova a
conversão.

**3. Procedência visível para o Leo, não só para o código.** A rodada 4 acertou em cheio: *"a procedência
existe para o código, não para o Leo"* — `19h` embutido e `19h` do servidor são idênticos na tela. Mostrar
`—` em tudo seria pior que hoje; mostrar sem dizer é a segunda fonte voltando pela janela. Meio-termo:

| Superfície | Com `Fonte.padrao` |
|---|---|
| Mesa, Home, Fechar, Tarefas | Renderizam o embutido, **e o app mostra um indicador discreto de `valores padrão · sem conexão`** — um só, no nível do app, não um selo por número |
| **Como funciona** | `—` e a nota *"ainda não li os valores do servidor"*. A tela cuja razão de existir é ser confiável nunca apresenta um embutido como se fosse o valor do sistema |

O indicador some no primeiro `fresco` ou `cache`.

#### Comparação de hora é por minuto, nunca por `getHours()`

`actionForAt` compara `now.getHours()` com inteiros. Com o horário virando parâmetro, isso quebra no primeiro
rito com minuto não-zero: shutdown às **18:30** ativaria às 18:00 ou às 19:00, dependendo do arredondamento — e
um teste que só troca horas inteiras não pegaria.

Toda comparação passa a ser em **minutos desde a meia-noite** (`minutos("18:30") === 1110`), e o teste 10
exercita o instante anterior, o exato e o posterior de um rito com minuto não-zero.

#### D11 — o que deriva e o que não deriva

`homeAction.actionForAt` usa hora como **fluxo de controle**, não só como texto:

| Linha | Condição | Deriva? |
|---|---|---|
| 116 | `hour < 8 && !template` | **Não.** É um **prazo** para abrir o dia, não o horário do toque (05:30) |
| 119 | `hour < 12 && !checkin.feito` | **Não.** Prazo do check-in, não o horário dele (08:20) |
| 122 | `reading > 0 && hour < 19` | **Sim** → `shutdown` |
| 125 | `sunday && hour >= 17` | **Sim** → `review − 3h` |
| 128 | `hour >= 19 && hour < 21` | **Sim** → `shutdown` e `fechamento` |
| 131 | `hour >= 21` | **Sim** → `fechamento` |

Em v3 eu deixei a linha 125 fixa **e ao mesmo tempo a descrevi** como "antecedência de 3h para o review das
20h". Nomear a relação e não derivá-la é criar exatamente a divergência que a fatia combate: mudar o review
para 18h deixaria o hero sugerindo review a partir das 17h, uma hora antes do que a própria descrição promete.
Derivar `review − 3h` dá **17:00 hoje** — comportamento idêntico, relação preservada.

**Virada de dia:** `review − 3h` com o review às `01:00` daria limiar negativo, ou deveria começar às `22:00`
de sábado — enquanto o `sunday` do código é calculado sobre o instante atual. Em vez de implementar rollover de
dia da semana para um caso que não existe, o contrato **proíbe rito semanal antes das `03:00`**, validado no
`ritos.py` (teste 6). Restrição explícita vale mais que rollover que ninguém vai exercitar; se um dia houver
review de madrugada, o teste avisa em vez de o hero errar em silêncio.

As duas que ficam fixas não referenciam rito nenhum: são prazos (*"abra o dia antes das 8"*, *"faça o check-in
antes do meio-dia"*). O comentário no código passa a dizer **prazo**, não "janela de antecedência", para não
repetir o erro de nomear uma relação que não existe.

`actionForAt` ganha o parâmetro `ritos`, no estilo de `montarMesa(sinais, points)`; os testes existentes passam
a tabela explicitamente.

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

### 3.5 Dois módulos puros, um por fatia

Em v4 eu pus `Params`, `Fonte`, `validar` e `decidir` dentro de `wikiResolve.ts` e listei esse arquivo como
entrega da **1B** — enquanto o provider, que é **1A**, depende de todos eles. A divisão em duas fatias que eu
tinha acabado de criar não compilava. A rodada 4 pegou.

Separação corrigida, pela fronteira real: **parâmetros** × **conteúdo**.

| Módulo | Fatia | O que faz |
|---|---|---|
| `app/src/parametrosCore.ts` | **1A** | `Params`, `Fonte`, `Decisao`, `DEFAULT_PARAMS`, `validar`, `decidir`, `aplicar`, `minutos`, `fonteParaWiki` |
| `app/src/wikiResolve.ts` | **1B** | `resolver`, `paginaPronta` — só resolução de texto, e importa tipos do core |

#### `parametrosCore.ts`

Em v1 a resolução morava dentro do componente e nenhum teste a exercitava. Extraída, no padrão de
`mesaView.ts` / `closingPoints.ts`. Não há teste de render de React Native neste projeto e esta fatia não vai
introduzir um — por isso **a decisão de qual fonte usar também é pura**, e não estado de componente.

```ts
export type Params = { /* espelha o schema */ };

export type Fonte =
  | { tipo: "fresco";       params: Params }
  | { tipo: "cache";        params: Params; salvoEm: string }   // ISO-8601 parseável
  | { tipo: "padrao";       params: Params }                    // o embutido, declarado (§3.3)
  | { tipo: "indisponivel"; motivo: "sem-cache" | "sessao" };

export type Entrada = {
  resposta: { ok: true; corpo: unknown } | { ok: false; status: number | null };
  cache: unknown;                                   // o que veio do storage, cru
};

// A decisão inclui o EFEITO, não só a fonte.
export type Decisao = { fonte: Fonte; cache: "gravar" | "manter" | "descartar" };

export const DEFAULT_PARAMS: Params;                      // completo, validado pelo teste 8

export type PortaCache = {                                // TUDO assíncrono — ver abaixo
  ler(): Promise<unknown>;
  gravar(v: unknown): Promise<void>;
  apagar(): Promise<void>;
};

export function validar(bruto: unknown): Params | null;   // null se o formato não bate
export function decidir(e: Entrada): Decisao;             // toda a política de §6, pura
export function aplicar(d: Decisao, p: PortaCache): Promise<void>;
export function minutos(hora: string): number;            // "18:30" → 1110
export function fonteParaWiki(f: Fonte): Fonte;           // padrao → indisponivel
```

`aplicar` recebe o armazenamento como **porta**, então a execução do comando de cache é testável com um duplo
— em v4 ela ficava no wiring do provider, que era o último pedaço de política sem teste.

**A porta é assíncrona, e isso não é detalhe.** Em v5 eu a declarei síncrona (`gravar(v): void`). Não é
implementável: `app/src/storage.ts` embrulha o `expo-secure-store` e **todas** as suas operações devolvem
`Promise` (`getItemAsync`, `setItemAsync`, `deleteItemAsync`). Um duplo síncrono passaria no teste enquanto a
produção não esperaria a persistência — teste verde sobre código que perde escrita. O teste 5 cobre também
**rejeição** da porta (gravar falha → a tela continua com a fonte decidida, o erro não sobe) e **ordenação**
(duas decisões em sequência não podem gravar fora de ordem).

Três coisas que mudaram desde v2, cada uma fechando um buraco real:

**`Fonte` é união discriminada.** Em v2 era `{params, idade: string|null}`, e `idade: null` significava tanto
"resposta fresca" quanto "cache sem timestamp" — a tela podia apresentar cache como fresco. Agora `cache`
**exige** `salvoEm`, e `salvoEm` precisa **parsear como ISO-8601**: um envelope com `"salvoEm": "ontem"`
passaria numa checagem de tipo `string` e produziria um selo inválido, então é descartado.

**`decidir` devolve o efeito, não só a fonte.** Em v3 ela retornava `Fonte`, o que a impedia de provar as duas
regras mais importantes de §6 — *"substitui o cache"* e *"não toca no cache bom"*. Essa decisão voltava para o
wiring não testado. Agora vem no retorno, e **o provider executa o comando mecanicamente**, sem `if` próprio.

**`padrao` é uma fonte como as outras.** Não é `null`, não é ausência: é um valor com procedência, que cada
superfície aceita ou recusa segundo a política de §3.3.

`validar` é a mesma função na escrita e na leitura do cache. Payload que não valida nunca entra e nunca
substitui um bom.

O que sobra no `.tsx`: desenhar. Buscar, decidir, gravar e revalidar são do provider; a política é de `decidir`;
a navegação por slug é de `wikiNav.ts` (§7.12).

### 3.6 O contrato: schema derivado, não fixture artesanal

Em v2 o contrato era um exemplo de resposta commitado e uma comparação de **caminhos**. Duas falhas reais: não
via tipo (o BFF podia trocar `hora: "05:30"` por `hora: 530` e passar), e um array vazio não produzia caminho
nenhum, contradizendo a igualdade exata com um fixture não vazio.

O FastAPI já gera JSON Schema do modelo Pydantic. **Um schema, um arquivo, um consumidor de cada lado:**

- **`app/src/wiki-schema.json`** — o contrato. **Arquivo único**, no bundle. Em v5 eu citei dois caminhos
  diferentes (`app/tests/fixtures/wiki-schema.json` em §3.6 e `app/src/wiki-schema.json` em §8) sem nada que
  os igualasse; o implementador não teria como saber qual é o verdadeiro.
- Teste do BFF (§7.8) **regenera** do modelo, **normaliza** (abaixo) e exige igualdade com esse arquivo.
- O app valida contra o mesmo arquivo, em runtime e em teste.
- `app/tests/fixtures/wiki-parametros.json` continua existindo, mas só como **massa de teste**.

#### Normalização: o Pydantic não gera o dialeto que o caminhador lê

Em v5 eu mandei o caminhador implementar `type`, `properties`, `required`, `items`, `minItems`, `enum` e
`nullable`, e mandei o teste quebrar diante de qualquer outra palavra-chave. **As duas ordens juntas são
impossíveis de cumprir:** `model_json_schema()` emite `$defs` e `$ref` para os modelos aninhados (`tarifas`,
`punicao`, `ritos[]`…), e `anyOf: [{type: "string"}, {type: "null"}]` para `dia: str | None`. Regenerar o
contrato quebraria o próprio teste, sempre.

Correção: uma função de normalização (`bff/app/wiki_schema.py`, ~30 linhas) roda **entre** gerar e commitar, e
produz o dialeto plano:

| Do Pydantic | Normalizado |
|---|---|
| `$defs` + `$ref` | Definição **inlined** no ponto de uso; `$defs` removido |
| `anyOf: [X, {type: "null"}]` | `X` com `nullable: true` |
| `const: "x"` | `enum: ["x"]` |
| `title`, `description` | Removidos — são ruído de documentação, não contrato |

O que **sobrar** de palavra-chave desconhecida depois da normalização é erro do teste 8, e aí sim quebrar é o
comportamento certo: significa que o modelo ganhou uma construção que o caminhador não sabe validar. A regra de
v5 estava certa; faltava a etapa que a torna alcançável.

Caminho de array é `areas[]` / `ritos[].hora`: o schema descreve a forma do elemento, e cardinalidade fica de
fora. Array vazio é válido em geral, e a tela renderiza lista vazia com nota.

**Duas exceções à cardinalidade livre**, porque o conteúdo depende delas:

- `niveis.limiares` tem **`minItems: 1`**. Um payload com `[]` seria válido e cacheado enquanto a página
  `pontos` afirma "a caminho do N1" — um nível que não existiria. Como o token `N1…Nn` é validado contra o
  comprimento dessa lista (§4.2), lista vazia torna o conteúdo obrigatório impossível.
- `ritos` tem **`minItems: 1`**. Sem nenhum rito, a pergunta de aceite `g` não tem resposta e o `homeAction`
  perde os limiares que passou a derivar (§3.3).

**O schema é o validador, não só o contrato.** Em v4 eu tinha `validar()` escrito à mão em TypeScript e um
teste tentando provar que ele concordava com o schema. A rodada 4 apontou o óbvio: comparar duas
implementações numa tabela selecionada **não prova equivalência** — e manter as duas é o único ponto
evitavelmente caro da spec.

Correção: **o schema commitado entra no bundle e `validar()` passa a ser um caminhador sobre ele**, não uma
segunda implementação das regras. Uma implementação, nada a provar.

O caminhador cobre só o subconjunto **normalizado** (abaixo) — `type`, `properties`, `required`, `items`,
`minItems`, `enum`, `nullable` — em torno de 60 linhas, sem dependência externa (o projeto não tem libs de
validação e esta fatia não vai introduzir uma).

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
3. **Todo o resto é proibido**, inclusive **por extenso**.

A blocklist de numerais escritos não pode ser "`vinte`, `oitenta`, … " com reticências — reticência não é
especificação, e a rodada 3 apontou que ordinais e frações ficavam de fora. Ela é **enumerada e fechada**, mora
ao lado do teste, e cobre quatro famílias:

| Família | Cobertura |
|---|---|
| Cardinais | `zero`, `um`…`vinte`, `trinta`, `quarenta`, `cinquenta`, `sessenta`, `setenta`, `oitenta`, `noventa`, `cem`, `cento`, `duzentos`…`novecentos`, `mil`, `milhão`, `milhões`, `bilhão`, `bilhões` |
| Ordinais | `primeiro`…`vigésimo` (e femininos) |
| Frações e multiplicativos | `meio`, `meia`, `metade`, `terço`, `quarto`, `dobro`, `triplo`, `quádruplo` |
| Coletivos de tempo | `dezena`, `dúzia`, `quinzena`, `trimestre`, `semestre` |

O teste casa palavra inteira, sem acento-sensibilidade, e ignora ocorrências dentro de slot. Toda entrada nova
na lista exige uma linha de comentário dizendo qual número ela protege — lista sem motivo apodrece.

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

**Renomeações:** nenhuma, em lugar nenhum. A v6 cancelou a renomeação `closing` → `fechamento` que as versões
anteriores mandavam fazer (§3.2).

## 6. Falhas e cache

Toda esta política vive em `decidir()` (§3.5) e é testada como função pura — **incluindo o efeito no cache**,
que é a coluna que em v3 ficava no wiring.

| Situação | `Fonte` | Cache | O que a wiki mostra |
|---|---|---|---|
| 200 e valida | `fresco` | `gravar` | Números, sem selo |
| 200 e **não** valida | `cache` ou `indisponivel` | `manter` | Tratada como falha. **O cache bom não é tocado** |
| Falha de rede, com cache | `cache` | `manter` | Números + selo `valores de 10/ago/2026` |
| Falha de rede, sem cache | **`padrao`** | `manter` | Na wiki: `—`, aviso e botão `tentar de novo` (o `fonteParaWiki` converte). Nas outras telas: o embutido + indicador |
| 401, com cache | `cache` | `manter` | Cache + nota "sessão expirada — entre em Ajustes para atualizar os valores" |
| 401, sem cache | `indisponivel: "sessao"` | `manter` | `—` + a mesma nota. **A wiki nunca expulsa para o login** — é tela de referência, e expulsar quem só quer ler é hostil. É o único caso de `indisponivel` que `decidir` produz, e o app já está em fluxo de login |
| Cache corrompido, sem `salvoEm`, ou `salvoEm` não-ISO | conforme a resposta | `descartar` | Cai no caso "sem cache" |
| **Precedência** | — | — | **Resposta válida sempre `gravar`.** `descartar` só quando não há resposta válida. Em v4 um 200 válido com cache corrompido casava com as duas linhas, e a implementação podia apagar em vez de persistir o valor fresco |
| Nada ainda: primeira abertura, sem rede | `padrao` | `manter` | Mesmo caso da linha "falha de rede, sem cache" acima — não são estados diferentes |
| Lista vazia onde é permitido | qualquer | — | Bloco com nota "não consegui ler a lista", não erro |


**Quem produz `padrao`, e por que não é o provider.** Até a v6 o §6 mandava `decidir` devolver
`indisponivel: "rede"` para rede caída sem cache, enquanto o §10.6a exigia que Mesa e Home mostrassem o
embutido — o que só `padrao` permite. Como `decidir` não recebia `DEFAULT_PARAMS`, as duas ordens eram
incompatíveis, e o implementador seria empurrado a resolver **dentro do provider**, que é onde §3.3 proíbe que
exista política. Corrigido: **`decidir` importa `DEFAULT_PARAMS` e devolve `padrao` ela mesma.** O provider
continua sem um `if` seu.

Efeito colateral bom: o motivo `"rede"` some do tipo. Sobram dois estados de `indisponivel`, e os dois são
alcançáveis — `"sessao"` vem de `decidir`, `"sem-cache"` vem só do `fonteParaWiki`.

**O texto nunca falha** — mora no bundle. A wiki abre sempre; o que pode faltar são os números, e quando faltam
ela diz **de onde não veio**.

**Cache — last-known-good validado.** Três regras:

1. **Só grava depois de `validar()` passar.** Um 200 parcial num rollout incompatível não pode sobrescrever um
   cache completo.
2. **Não expira.** Expirar deixaria o Leo sem números justamente offline. Quem carrega a honestidade é a
   origem explícita (`Fonte.tipo`) e o selo com **dia, mês e ano**.
3. **Revalida ao ganhar foco**, não só ao montar, mais o botão `tentar de novo`.

## 7. Testes

Quinze. Os cinco primeiros são o que faz o aceite ser verdade em vez de promessa.

| # | Arquivo | O que prova |
|---|---|---|
| 1 | `app/tests/wikiContent.test.mjs` | **Slot órfão** — todo `{...}` existe no schema (§3.6), com o tipo certo |
| 2 | idem | **Literal proibido** — dígito fora de slot que não caia nas três categorias de §4.2 quebra; inclui a blocklist enumerada de numerais por extenso |
| 3 | idem | **Valores-sentinela** — renderiza todas as páginas com um `Params` em que cada número é um sentinela distinto, e falha se qualquer valor de produção aparecer no texto. Pega o número copiado à mão que casualmente bate com o real |
| 4 | idem | **Inventário coberto** — todo slot de §4.2 é usado por alguma página; e todo slug de `ritos.json` tem `RITOS_TEXTO` com `nome`/`pede`/`grava` não vazios |
| 5 | `app/tests/parametrosCore.test.mjs` | **`decidir`** nos casos de §6, conferindo **fonte, comando de cache e a precedência**; **`validar`** com payload completo, parcial, tipo errado, array vazio, `null`, cache sem `salvoEm` e com `salvoEm` não parseável; **`aplicar`** contra uma porta **assíncrona** em memória, provando `gravar`/`manter`/`descartar`, mais **rejeição** da porta e **ordenação** de duas decisões seguidas; **`minutos`**. Nenhum caminho devolve `undefined` |
| 6 | `bff/tests/test_ritos.py` | `ritos.json` carrega e valida: `slug` único, **`task` único**, `hora` `HH:MM`, `dia` válido, `script ∈ {nudge,digest}`, **rito semanal não antes de `03:00`** (§3.3); e o `ValidateSet` do `nudge.ps1` **e as chaves do `NUDGE_COPY`** são, os dois, exatamente os slugs com `script: "nudge"` — igualdade nas duas direções, não continência |
| 7 | idem | **`NUDGE_COPY` ligado ao slug certo** — renderiza cada copy com uma hora sentinela **distinta por slug** e exige que cada texto mostre a sua. Em v3 o teste só provava ausência de literal: o fechamento podia interpolar a hora do shutdown e passar, anunciando a hora errada no push |
| 8 | `bff/tests/test_wiki_parametros.py` + `app/tests/parametrosCore.test.mjs` | 401 sem token; cada valor vem de `settings`/`ritos.py` (muda o setting → muda a resposta); o JSON Schema regenerado **e normalizado** (§3.6) é idêntico a `app/src/wiki-schema.json`; a normalização não deixa `$ref`, `$defs`, `anyOf`, `const`, `title` nem `description`; o que sobra está todo no subconjunto do caminhador; e **`DEFAULT_PARAMS` valida contra o schema** |
| 9 | `bff/tests/test_sync_cron.py` | O plano do `sync-cron.ps1 -DryRun` bate com o `ritos.json`: sete tasks, gatilho certo (`-Daily` × `-Weekly -DaysOfWeek Sunday`), script certo; task `Aeternum *` ausente do JSON entra na lista de remoção e `Aeternum BFF` não; e a **política de falha** de §3.2 (JSON inválido aborta; erro do Agendador não impede o boot e gera alerta) |
| 10 | `app/tests/homeAction.test.mjs` | Os quatro limiares que derivam (§3.3) mudam quando a tabela `ritos` muda, incluindo o domingo em `review − 3h`; os dois prazos **não** mudam. Com um rito em minuto não-zero (`18:30`), o instante anterior, o exato e o posterior caem no ramo certo |
| 11 | `app/tests/migracaoPoints.test.mjs` | **Guarda estática:** nenhum arquivo fora de `theme.ts` e `parametros.tsx` importa `POINTS`. Sem ela, um call site esquecido passa despercebido e o aceite §10.2 ainda fica verde |
| 12 | `app/tests/wikiNav.test.mjs` | Navegação por slug: slug válido, slug desconhecido, ausência de slug (abre o índice), e voltar do último nível sai da tela |
| 13 | `app/tests/mesaView.test.mjs` | `comofunciona` em `TODOS_OS_DESTINOS` (11 → 12) e nas três asserções de ordem; e a hora exibida vem do parâmetro `ritos`, não de literal |
| 14 | `app/tests/parametrosCore.test.mjs` | **`fonteParaWiki`** converte `padrao` em `indisponivel` e deixa `fresco`, `cache` e `indisponivel` intactos. Em v4 a recusa da wiki era convenção — um `switch` esquecido mostraria embutido e tudo passava |
| 15 | `app/tests/wikiResolve.test.mjs` | **`resolver`** com slot presente, ausente e malformado; **`paginaPronta`** com cada tipo de bloco, com `Fonte.indisponivel` (tudo vira `—`) e com rito sem entrada em `RITOS_TEXTO` (o fallback de §3.4). Nenhum caminho devolve `undefined` |

**Correção ao que o B2 diz:** o backlog avisa que isto "muda a contagem de 11 destinos e o teste de 2160
combinações". As 2160 (`mesaView.test.mjs:86`) são `5 × 4 × 3 × 3 × 3 × 4`, o produto das **combinações de
sinais** — não têm relação com quantos destinos existem, e **continuam 2160**.

**O que nenhum teste cobre, e é honesto dizer:**

- **Se o texto está bom.** Nenhuma suíte prova que uma frase esclarece. Por isso o aceite (§10) é uma lista de
  perguntas concretas respondidas pelo Leo.
- **A composição visual do `.tsx`.** Depois de `decidir` (política), `aplicar` (efeito), o provider (busca) e
  `wikiNav` (navegação), o que resta no componente é desenhar — e disso não há teste automatizado, porque o
  projeto não tem infraestrutura de render de RN e criar uma é fatia própria (§14). Coberto pelo aceite manual
  §10.4. Em v3 esse buraco era maior e eu o declarei em vez de reduzi-lo; a rodada 3 apontou que dava para
  extrair mais, e deu.
- **O disparo da revalidação por foco.** Que o app revalide ao voltar do background é efeito de ciclo de vida
  de RN. O que ele faz **depois** de revalidar é `decidir` + `aplicar`, e isso é testado. O disparo em si é
  drill manual (§10.7).

## 8. Arquivos tocados

**Novos**

- `bff/ritos.json` · `bff/app/ritos.py` · `bff/scripts/sync-cron.ps1`
- `bff/tests/test_ritos.py` · `bff/tests/test_wiki_parametros.py` · `bff/tests/test_sync_cron.py`
- **1A:** `app/src/parametrosCore.ts` · `app/src/parametros.tsx` (o provider) ·
  `app/tests/parametrosCore.test.mjs` · `app/tests/migracaoPoints.test.mjs` ·
  `app/src/wiki-schema.json` (arquivo único do contrato, §3.6) ·
  `bff/app/wiki_schema.py` (a normalização)
- **1B:** `app/src/wikiContent.ts` · `app/src/wikiResolve.ts` · `app/src/wikiNav.ts` ·
  `app/src/screens/ComoFunciona.tsx` · `app/tests/wikiContent.test.mjs` ·
  `app/tests/wikiResolve.test.mjs` · `app/tests/wikiNav.test.mjs`

**Alterados**

- `bff/app/main.py` — rota nova; `NUDGE_COPY` interpola hora e nº de prioridades (slug `closing` **preservado**)
- `bff/scripts/install-cron.ps1` — passa a chamar `sync-cron.ps1`
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
- **Derivar os dois prazos do `homeAction`** (`hour < 8`, `hour < 12`) — não referenciam rito nenhum (D11).
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

**5. O nudge não quebrou.** Depois de o `NUDGE_COPY` passar a interpolar a hora, o nudge das 21h chega com o
texto certo. Drill manual, no aparelho.

**6a. Primeira abertura é honesta — fora da wiki (1A).** App recém-instalado, sem rede: Mesa e Home mostram o
embutido e funcionam, **e o indicador `valores padrão · sem conexão` está visível**. Ele some assim que uma
resposta ou um cache chega.

**6b. Primeira abertura é honesta — na wiki (1B).** Na mesma condição, `Como funciona` mostra `—` e diz
*"ainda não li os valores do servidor"*. Nenhuma tela apresenta o embutido como se fosse o valor do sistema.

**7. Revalidação por foco — drill manual (1B).** Abrir o app com o BFF desligado (números do cache, com selo),
ligar o BFF **sem sair da tela**, tirar o app do foco e voltar: o selo some e os números são os novos. É drill
porque disparar o evento de foco exige render de RN, que o projeto não testa (§7); está aqui em vez de fingir
cobertura.

**8. Suíte.** `python -m pytest -q` e os testes `.mjs` passam, incluindo os quinze de §7.

## 11. Complexidade

A rodada 1 recomendou cortar de nove páginas para quatro. Recusei, e a rodada 2 aceitou o argumento como
**sólido**: a infraestrutura é custo fixo, as cinco páginas extras são custo marginal, e este é o terceiro
pedido da mesma coisa — as duas primeiras vezes morreram por corte. Ressalva do revisor, justa: cada página
não custa "uma linha"; conteúdo e aceite dão trabalho real. Está refletido nas perguntas `l`, `m` e `n`.

O que a rodada 2 apontou como excesso era o **contrato artesanal** (Pydantic + validador TS + fixture manual +
comparação de caminhos, que ainda assim não garantia tipo). Aceito: §3.6 troca isso por schema derivado. É a
única parte da v3 que ficou **mais simples** que a v2.

O crescimento restante — provider, `sync-cron.ps1`, reconciliação, quinze testes — não é ornamento: é o preço de
a wiki não ser a sexta cópia. O revisor recomendou exatamente isso no veredito de complexidade da rodada 2.

**O que a rodada 3 cobrou, com razão, foi a etiqueta.** O veredito dela: *"a v3 virou duas fatias acopladas"*, e
o remédio não é cortar conteúdo nem migração — é **parar de chamar duas coisas de uma**. §12 responde a isso.

## 12. Duas fatias, não uma

Chamar tudo de "fatia 1" era ficção: o bloco de fonte única não tem tela nenhuma, é verificável sozinho, e
**entrega valor mesmo que a wiki nunca seja escrita** — hoje mudar um horário deixa quatro superfícies
mentindo. A wiki é a razão de a gente ter olhado, não a razão de valer a pena.

### Fatia 1A — Fonte única (pré-requisito verificável)

**Status: entregue em 11/ago/2026** — branch `wiki-1a`, commits `1ddfbf0..HEAD`. Os drills manuais no
aparelho (§10.5, §10.7) continuam **pendentes**, a cargo do dono do projeto.

| | |
|---|---|
| **Entrega** | `ritos.json`, `ritos.py`, `sync-cron.ps1` (reconciliação + `-DryRun` + política de falha), `NUDGE_COPY` interpolado, `start-bff.ps1` chamando o sync, `GET /wiki/parametros` + schema commitado, **`parametrosCore.ts`**, `ParametrosProvider`, o indicador de `padrao`, os 7 call sites de `POINTS.` e os 3 de hora |
| **Testes** | 5, 6, 7, 8, 9, 10, 11, 13, 14 |
| **Verificação** | Mudar uma hora no `ritos.json`, reiniciar, e ver **o Agendador, o push, a Mesa e o hero da Home** mudarem juntos. Mudar `pontos_por_rotina` e ver Mesa, Fechar e Tarefas mudarem. Aceite §10.2, §10.5 e §10.6a |
| **Fecha sozinha?** | Sim, **e agora de verdade**: em v4 o provider dependia de `validar`/`decidir`, que eu tinha listado na 1B — a fatia não compilava. O núcleo de parâmetros (§3.5) é da 1A |

### Fatia 1B — A tela (imediatamente depois)

| | |
|---|---|
| **Entrega** | `wikiContent.ts`, `wikiResolve.ts` (só resolução de texto), `wikiNav.ts`, `ComoFunciona.tsx`, as nove páginas, o item da Mesa, as duas portas contextuais |
| **Testes** | 1, 2, 3, 4, 12, 15 |
| **Verificação** | As 14 perguntas de §10.1, mais §10.3, §10.4 e §10.6b |
| **Depende de 1A?** | Sim, inteiramente. Sem o provider e o schema, a tela não tem de onde tirar número — e escrevê-los à mão é o que a fatia inteira existe para impedir |

**Não é para paralelizar.** 1A primeiro, verificada no aparelho, e só então 1B. A tentação de escrever as nove
páginas enquanto o encanamento não está pronto é exatamente como se produz um texto com número chumbado.

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
| CRÍTICO — renomear `closing` quebraria o `nudge.ps1` | Confirmado: `ValidateSet` na linha 1 mataria o rito das 21h antes do HTTP. **Resolvido na v6 cancelando a renomeação** (§3.2): `closing` é o vocabulário do BFF, não uma inconsistência. Fica o teste 6 vigiando a igualdade |
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

**v3 → v4** — rodada 3 (7 dos 8 achados da rodada 2 resolvidos; 3 dos 7 pendentes da rodada 1 resolvidos;
**nenhum achado crítico novo**; veredito mantido em `IMPLEMENTAR COM CORREÇÕES`):

| Achado da rodada 3 | Resposta |
|---|---|
| ALTO — provider sem autoridade única: ele hidratava e a tela também buscava | O provider é o **único** dono de fetch, validação, cache e revalidação; expõe `useParametros()` e `useRevalidar()` (§3.3) |
| ALTO — bootstrap era segunda fonte sem procedência | `padrao` vira variante declarada de `Fonte`; Mesa/Home aceitam, **a wiki recusa** e diz que ainda não leu o servidor (§3.3, §6) |
| ALTO — `decidir` não decidia o efeito no cache | Passa a devolver `{fonte, cache: gravar\|manter\|descartar}`, executado mecanicamente pelo provider (§3.5) |
| ALTO — `HH:MM` não cabe em `getHours()` | Comparação em minutos desde a meia-noite; teste 10 usa um rito em `18:30` e testa antes/no instante/depois |
| ALTO — migração dos 7 call sites sem guarda | Teste 11: nenhum arquivo fora de `theme.ts` e `parametros.tsx` importa `POINTS` |
| ALTO — `niveis.limiares: []` válido com `N1` obrigatório | `minItems: 1` em `niveis.limiares` e em `ritos` (§3.6) |
| ALTO — teste do `NUDGE_COPY` provava ausência, não ligação | Teste 7: hora sentinela **distinta por slug**; o fechamento interpolando a hora do shutdown agora quebra |
| ALTO — sync no boot sem política de falha | JSON inválido aborta; erro do Agendador não impede o boot e gera alerta (§3.2, teste 9) |
| MÉDIO — `salvoEm` não garantia ISO-8601 | Precisa parsear; `"ontem"` é descartado (§3.5, teste 5) |
| D11 julgada **parcialmente defensável** | Aceito: o domingo passa a derivar `review − 3h` (17:00 hoje, comportamento idêntico). Nomear a relação e não derivá-la era criar a divergência. Os dois que ficam são **prazos**, e o comentário no código deixa de chamá-los de antecedência |
| Buraco do `.tsx` — "o achado 11 sobrevive, menor" | Aceito: `wikiNav.ts` extraído e testado (teste 12). Sobra só o desenho, e §7 diz isso sem eufemismo |
| PARCIAL — blocklist com reticências não é especificação | Lista **enumerada e fechada** em quatro famílias, incluindo ordinais e frações (§4.2) |
| PARCIAL — equivalência `validar()` × schema não provada | Teste 8 percorre a mesma tabela de casos derivada do schema nos dois lados (§3.6) |
| Complexidade: *"virou duas fatias acopladas"* | Aceito. §12 vira **1A (fonte única) + 1B (a tela)**, com 1A como pré-requisito verificável que fecha sozinho |

**v4 → v5** — rodada 4 (7 dos 9 achados da rodada 3 resolvidos; **nenhum crítico**; e a resposta à pergunta
direta: *"não, a spec não passou a custar mais do que o problema que resolve, porque 1A corrige divergência
operacional já existente em várias superfícies"*):

| Achado da rodada 4 | Resposta |
|---|---|
| ALTO — a 1A dependia de código atribuído à 1B | Erro real: o provider precisa de `validar`/`decidir`, que estavam em `wikiResolve.ts`. Núcleo separado em `parametrosCore.ts` (1A) × `wikiResolve.ts` (1B), pela fronteira parâmetros × conteúdo (§3.5) |
| ALTO — `padrao` não era produzível pela assinatura | Erro real: `POINTS` não é um `Params`. `DEFAULT_PARAMS` completo, validado contra o schema (§3.3, teste 8) |
| ALTO — a política por superfície era convenção | `fonteParaWiki()` puro e testado (teste 14); a wiki lê a fonte só por ele |
| MÉDIO — precedência dos comandos de cache contraditória | Explícita: resposta válida sempre `gravar`; `descartar` só sem resposta válida (§6) |
| MÉDIO — aceite da 1A exigia tela que não existe | §10.6 dividido em **6a** (fallback e indicador, 1A) e **6b** (recusa da wiki, 1B) |
| MÉDIO — `review − 3h` sem virada de dia | Contrato proíbe rito semanal antes das `03:00`, validado no `ritos.py` (§3.3, teste 6) |
| PARCIAL — blocklist omitia `zero`, `milhão`, ordinais além de décimo | Lista estendida (§4.2) |
| PARCIAL — equivalência entre validador e schema não é prova | Aceito, e simplifica: **o schema vira o validador em runtime** (caminhador de ~60 linhas sobre o subconjunto usado). Uma implementação, nada a provar (§3.6) |
| PARCIAL — `padrao` era segunda fonte sem sinal para o Leo | Aceito: *"a procedência existe para o código, não para o Leo"*. Indicador discreto de `valores padrão · sem conexão` nas superfícies que aceitam (§3.3) |
| PARCIAL — execução do comando e refresh sem teste | `aplicar(decisao, storage)` com porta de armazenamento, testado com duplo em memória (§3.5, teste 5) |
| PARCIAL — igualdade das chaves do `NUDGE_COPY` | Igualdade nas duas direções com os slugs `script: "nudge"`, não continência (teste 6) |
| D11 julgada **fechada** | Sem mudança, além do rollover acima |

**v5 → v6** — rodada 5. Os **6 achados da rodada 4 e 4 dos 6 parciais: resolvidos**. Mas duas das minhas
correções de v5 **pioraram** o que consertavam, e a resposta à pergunta que importa foi **não**:

| Achado da rodada 5 | Resposta |
|---|---|
| **PIOROU** — o caminhador não aceita o schema que o Pydantic gera | Erro meu, e do tipo pior: eu mandei implementar um dialeto e mandei o teste quebrar diante de qualquer outro, sem notar que `model_json_schema()` emite `$defs`, `$ref`, `anyOf` e `const`. O teste era impossível de passar. Entra a normalização de §3.6 |
| **PIOROU** — porta de cache síncrona sobre armazenamento assíncrono | Erro meu: `storage.ts` embrulha o `expo-secure-store` e devolve `Promise` em tudo. Porta e `aplicar` viram assíncronos; o teste 5 cobre rejeição e ordenação |
| MÉDIO — dois arquivos canônicos para o mesmo schema | Erro meu de v5: citei `app/tests/fixtures/wiki-schema.json` em §3.6 e `app/src/wiki-schema.json` em §8. Arquivo único: `app/src/wiki-schema.json` |
| PARCIAL — revalidação por foco sem cobertura | Aceito como drill manual explícito (§10.7), não como teste inexistente. O que vem **depois** do foco é `decidir` + `aplicar`, e isso é testado |
| *"Um implementador consegue construir sem voltar a perguntar?"* → **NÃO** | Ele travaria nos três pontos acima. É a razão de existir a v6 |


**Correção da v6 encontrada ao planejar a implementação:** a renomeação `closing` → `fechamento`, que as versões
1–5 mandavam fazer, foi **cancelada**. `closing` é o vocabulário estabelecido do BFF (rotas, evento, kind de
notificação, `Literal`); renomear só o nudge criaria um racha novo em vez de fechar um. Isso elimina a migração
mais arriscada da 1A — o achado CRÍTICO da rodada 2 deixa de existir em vez de ser gerenciado. Ver §3.2.

## 14. Fatias seguintes

| Fatia | O quê | Por que depois |
|---|---|---|
| 2 | Diagramas dos fluxos principais | Custo de layout real; o aceite não pede diagrama |
| 3 | Infraestrutura de teste de render de RN | Fecharia o buraco declarado em §7; vale para o app todo, não só a wiki |
| 4 | Links "o que é isso?" nas demais telas | Aditivo; só faz sentido com 1B no ar |

### 14.1 Herdado da 1A para a 1B — dois campos servidos que ninguém lê

A revisão final da 1A encontrou isto, e a 1B é quem tem que resolver, porque é ela quem vai **exibir**
esses números.

**`shutdown.prioridades` é servido pela rota e não tem um consumidor.** O `3` continua escrito à mão em
seis lugares, um deles no mesmo arquivo que declara a constante:

| Onde | O quê |
|---|---|
| `bff/app/main.py:589` | `if len(limpas) > 3: raise ValueError("máximo 3 prioridades")` — 530 linhas abaixo de `PRIORIDADES_SHUTDOWN` |
| `app/src/homeAction.ts:153` | *"Pendências, follow-ups e três prioridades de amanhã."* — por extenso |
| `app/src/screens/Shutdown.tsx:21,134,155` | `[0,1,2]`, `"AS 3 PRIORIDADES DE AMANHÃ"`, `[0,1,2]` |
| `app/src/api.ts:654` | `prioridades.slice(0, 3)` |

Mude `PRIORIDADES_SHUTDOWN` para 4 e o push anuncia 4, a rota diz 4, o hero da Home diz "três", a tela
desenha 3 campos, e o `POST /shutdown` **rejeita** a quarta. É o padrão das cinco cópias se formando de
novo — desta vez dentro da fatia que existe para matá-lo.

**`areas` idem:** servido pela rota, e `app/src/screens/Tasks.tsx:25-28` tem a lista copiada à mão. Uma
11ª área em `bff/app/tasks.py:21` faria o BFF agrupar por ela enquanto o seletor de nova tarefa não a
oferece. Conserto de uma linha: `useParams().areas`.

**Menor, da mesma família:** `app/src/ui.tsx:468` tem `[1, 2, 3, 4]` chumbado para os diamantes,
enquanto `niveis.limiares` já vem do servidor. Um 5º limiar em `config.py` mostraria 4 diamantes.

### 14.2 Dívida conhecida da 1A

- **A antecedência de 3h do review está escrita duas vezes, em duas linguagens:**
  `app/src/homeAction.ts` (`em("review") - 180`) e `bff/app/ritos.py` (`_MIN_SEMANAL = 3 * 60`). O
  comentário do `ritos.py` diz que a validação existe para proteger o `-180`; mude a antecedência para
  4h e um review às 03:30 passa na validação e produz limiar às 00:30 — hero de revisão o domingo
  inteiro.
- **`horaCurta` tem três implementações** (`ritos.py`, `mesaView.ts`, `homeAction.ts`). As três
  concordam byte a byte; as duas do TS são inerentes à regra de módulo puro sem import de valor.
- **O indicador de procedência usa `fonts.mono`**, enquanto o irmão na mesma tela usa outro estilo. Não
  consertado de propósito: o trabalho de identidade visual em andamento reestiliza a Home inteira.
- **`bff/app/routines.py:38`** tem a rotina-semente `("acordar-5h30", "acordar 5h30", …)`. Mover o toque
  para 06:00 deixa a rotina com o nome velho. **Não é defeito**: rótulo de rotina é dado editável do
  usuário, e a rotina ("acordar") é coisa diferente do rito (o toque que avisa). Registrado porque é o
  tipo de divergência que esta fatia treina o olho para ver.
