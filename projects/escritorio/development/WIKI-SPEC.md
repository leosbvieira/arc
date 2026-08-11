# Wiki do sistema — tela "Como funciona" (fatia 1)

> **Origem:** item **B2** do `AETERNUM-P2-BACKLOG.md` — *"precisamos de uma página que mostra como funciona o
> app, o que são diamantes, pontos, etc"* / *"sistema inteiro, tipo um wiki"* / *"pode ser pela mesa"*
> (Leo, 09/ago/2026). Terceiro pedido: já constava na SPEC como "Manual/SOP" (§7) e no corte
> "diagramas derivados do vault → tooltips + cheatsheet estático".
>
> **Data do spec:** 10/ago/2026. **Estado:** aprovado seção a seção pelo Leo; não implementado.
>
> Este documento é a spec de **uma fatia**. Fatia 2 (diagramas) e fatia 3 (fim do hardcode de pontos)
> estão em §11, fora de escopo aqui.

---

## 1. O problema

O autor do sistema não consegue ler o próprio app. Duas evidências no mesmo dia, ambas com o celular na mão:

- *"o que significa 'a caminho do N1'?"* e *"os diamantes apagados estão certos?"* — pré-voo de 09/ago.
- *"as ideias que eu tenho, ou lembranças de tarefas? olhei pro meu quarto e lembrei de comprar cueca,
  com qual IA eu falo isso?"* — a **Captura rápida** é exatamente isso, é o fluxo principal do sistema,
  funciona, e nada na tela diz o que ela é.

A segunda pergunta expõe uma confusão estrutural: **há duas IAs com contratos opostos** e o app não diz qual
serve pra quê. Captura é assíncrona e fire-and-forget (você joga fora da cabeça, o worker classifica depois);
Mentor é síncrono e conversacional.

O `AETERNUM-MAPA-DO-SISTEMA.md` já existe e não resolveu — foi escrito pro leitor errado (é material de dev).
As seções 1–6 dele são a **semente de conteúdo**; as 7 e 8 (rotas do BFF, módulos) **não entram**.

## 2. Decisões travadas

Todas confirmadas pelo Leo em 10/ago, antes do design.

| # | Decisão | Alternativas descartadas |
|---|---|---|
| D1 | **Só tela no app.** Não há manual `.md` paralelo. | Tela + doc versionado (dobra a superfície); só doc (é o que já falhou) |
| D2 | **Nome: "Como funciona".** Mesmo nome na porta, no título e no destino. | "Wiki" (promete busca e muitas páginas); "Manual" (soa a doc que ninguém abre) |
| D3 | **Porta: ARQUIVO da Mesa** — decisão do Leo no B2. | — |
| D4 | **Índice + páginas de tópico**, não tela única rolável. | Rolagem única (ninguém rola 8 seções no celular, e não dá âncora); só tooltips (é o corte que já falhou 2×) |
| D5 | **Números vêm de uma rota nova `GET /wiki/parametros`.** | Reusar rotas existentes (nenhuma expõe tarifa/limiar/horário); texto fixo agora (vira o terceiro lugar que mente) |
| D6 | **Texto mora no app**, em `wikiContent.ts`, com slots. | Texto no BFF (cópia de UI no Python; wiki morre com o BFF); markdown no vault (exige parser + sincronia) |
| D7 | **Cache com selo de data**; sem cache, traço. | Sem cache (inútil offline, que é quando mais importa); cache silencioso (é o "discordar em silêncio" que a reconciliação `93a5783` matou) |
| D8 | **Sem diagramas nesta fatia.** | Diagramas em RN (layout caro, some no celular estreito); imagens geradas no batch (cria o rito de manutenção que a SPEC dizia não querer) |
| D9 | **Horários dos ritos: `config.py` declara, teste guarda o cron.** Ver §3.2. | Cron lendo o config via `python -c` (acopla o instalador ao venv); horário como prosa (proibido pelo B2) |
| D10 | **`theme.ts:POINTS` não é tocado nesta fatia.** Fica como dívida registrada. | Matar o hardcode junto (encosta em 4 telas + testes; a wiki deixa de ser a entrega) |

### 2.1 A restrição dura

**Nenhum número pode ser prosa.** Tarifa, limiares de nível, horários dos ritos, tamanho do ciclo, dias do
staging e a lista de áreas são **lidos do BFF e renderizados**. Se a wiki escrever "rotina vale 20", ela vira o
terceiro lugar que pode mentir — e a reconciliação da economia (`93a5783`) existiu porque dois lugares
discordavam em silêncio.

## 3. Arquitetura

Três peças, uma responsabilidade cada.

```
config.py (settings)  ──►  GET /wiki/parametros  ──►  ComoFunciona.tsx  ──►  cache local
        │                     (só números)                  │
        └──► install-cron.ps1                        wikiContent.ts
             (verificado por teste)                    (só texto + slots)
```

### 3.1 `GET /wiki/parametros` — BFF, rota nova em `main.py`

Autenticada (Bearer, igual às demais), **read-only**, sem estado do usuário. Devolve só o que é parâmetro do
sistema. Saldo, nível atingido e progresso continuam em `/pontos` — esta rota responde *"como o sistema
funciona"*, não *"como você está"*.

Todo valor é derivado de `settings` ou de constante já canônica no BFF. **Nenhum literal na rota.**

```jsonc
{
  "tarifas":  { "rotina": 20, "tarefa": 10, "captura": 5,
                "fechamento": 80, "shutdown": 30, "despejo": 40 },
  "punicao":  { "limiar_furos": 3, "desconto_padrao": 60, "teto_semanal": 200 },
  "niveis":   { "limiares": [700, 1700, 3400, 6800] },
  "ciclo":    { "semanas": 12, "inicio": "2026-07-06" },
  "staging":  { "dias_para_alerta": 3 },
  "areas":    ["Trabalho", "Staging", "Corpo", "Saúde Mental", "Responsabilidade",
               "Finance", "Carreira", "Estudo", "Relacionamentos", "Lazer"],
  "ritos":    [ { "slug": "toque",      "nome": "Toque",        "hora": "05:30" },
                { "slug": "checkin",    "nome": "Check-in",     "hora": "08:20" },
                { "slug": "jornal",     "nome": "Jornal",       "hora": "08:30" },
                { "slug": "digest",     "nome": "Digest",       "hora": "09:00" },
                { "slug": "shutdown",   "nome": "Shutdown",     "hora": "19:00" },
                { "slug": "fechamento", "nome": "Fechar o dia", "hora": "21:00" },
                { "slug": "review",     "nome": "Review",       "hora": "20:00", "dia": "domingo" } ]
}
```

**Ordem de `ritos`:** os diários em ordem cronológica, e os semanais (hoje só o review) **depois deles**. A
tela renderiza na ordem recebida — o BFF é quem decide, não o `wikiContent.ts`.

Procedência de cada campo (valores acima são os de 10/ago; **a rota é a verdade, não este documento**):

| Campo | Fonte |
|---|---|
| `tarifas.*` | `settings.pontos_por_rotina`, `_tarefa`, `_captura`, `_fechamento`, `_shutdown`, `_despejo` |
| `punicao.limiar_furos` | `settings.routine_miss_threshold` |
| `punicao.desconto_padrao` / `teto_semanal` | `settings.desconto_padrao` / `settings.teto_desconto_semanal` |
| `niveis.limiares` | `settings.nivel_limiares` |
| `ciclo.*` | `settings.ciclo_semanas` / `settings.ciclo_inicio` |
| `staging.dias_para_alerta` | `settings.staging_age_days` |
| `areas` | `bff/app/tasks.py:AREAS` (lista canônica já existente) |
| `ritos` | `settings.ritos` — **campo novo**, ver §3.2 |

### 3.2 Os horários dos ritos não existiam no BFF

Achado durante o design: `config.py` **não tem** os horários. Eles vivem só em
`bff/scripts/install-cron.ps1`, como gatilhos do Agendador de Tarefas do Windows. O BFF não sabe que horas ele
mesmo acorda.

Então "horário lido do BFF" não é ler algo que existe — é **criar** a fonte:

1. `config.py` ganha `ritos: list[dict]` com os sete ritos (slug, nome, hora, e `dia` só no review).
2. `install-cron.ps1` **não muda** — continua com os `-At` literais.
3. Um teste Python lê o `.ps1`, extrai os pares `TaskName` × `-At HH:MM`, e falha se divergirem de
   `settings.ritos`. O config vira a verdade declarada; o script, o consumidor verificado.

Mapa `TaskName` → `slug` usado pelo teste: `Aeternum Toque`→`toque`, `Aeternum Check-in`→`checkin`,
`Aeternum Jornal`→`jornal`, `Aeternum Digest`→`digest`, `Aeternum Shutdown`→`shutdown`,
`Aeternum Fechamento`→`fechamento`, `Aeternum Review`→`review`. A tarefa `Aeternum BFF` **é ignorada**: ela
dispara no boot e não tem `-At`.

Descartado: fazer o `.ps1` ler o config via `python -c`, que acopla o instalador do cron ao venv e quebra no
dia em que o ambiente for reconstruído.

### 3.3 `app/src/wikiContent.ts` — o texto

Dado puro, sem JSX e **sem import de valor** — mesmo padrão do `mesaView.ts`, para o teste em `.mjs` conseguir
importar sem resolver caminho relativo em runtime.

```ts
export type Bloco = { tipo: "p" | "passo" | "nota"; texto: string };
export type Pagina = { slug: string; titulo: string; resumo: string; blocos: Bloco[] };
export const PAGINAS: Pagina[] = [ /* ... */ ];
```

Números entram como slots no texto: `"Cada rotina marcada vale +{tarifas.rotina}."` O slot é um caminho
pontuado dentro da resposta de `/wiki/parametros`. Arrays usam índice (`{niveis.limiares.0}`) ou o helper de
lista (§4.1).

### 3.4 `app/src/screens/ComoFunciona.tsx` — a tela

Índice e páginas de tópico, no estilo visual das telas existentes. Busca os parâmetros uma vez ao montar,
grava em cache local, resolve os slots na renderização. Estado de navegação interno (índice ↔ página); o
chevron do header volta uma página por vez e, no índice, sai da tela.

### 3.5 O contrato entre Python e TypeScript

O teste de slot órfão (§7.1) roda em `.mjs` e precisa saber quais caminhos a rota Python devolve. Um lado não
importa o outro, então o contrato é **um arquivo versionado no meio**:

`app/tests/fixtures/wiki-parametros.json` — uma resposta de exemplo completa, commitada, com os valores de
`config.py` no momento do commit.

- O teste **do app** (§7.1) valida os slots contra as **chaves** deste arquivo.
- O teste **do BFF** (§7.3) chama a rota e exige que o **conjunto de caminhos** da resposta real seja idêntico
  ao do fixture — valores podem divergir (é o esperado quando alguém muda um setting), **formato não**.

Assim, tirar um campo da rota quebra o teste do BFF, e citar um campo que não existe quebra o teste do app.
Nenhum dos dois depende de rodar a outra linguagem.

## 4. As oito páginas

Cada página existe porque responde uma pergunta que o Leo fez de verdade, ou porque o aceite do B2 exige.

| Slug | Título | O que ela mata | Slots |
|---|---|---|---|
| `comece` | Comece por aqui | O que é o app em 30s: as três camadas, as três leis, e um mapa "quero X → vou em Y" | — |
| `captura` | Captura rápida | *"lembrei de comprar cueca, com qual IA falo isso?"* — é aqui, é um toque, o worker classifica depois | `tarifas.captura` |
| `duas-ias` | As duas IAs | O contrato oposto: Captura assíncrona e fire-and-forget × Mentor síncrono e conversacional, com exemplos lado a lado | — |
| `pontos` | Diamantes e pontos | *"o que significa 'a caminho do N1'"*, *"os diamantes apagados estão certos?"* — o que paga, quanto, o que desconta, nível é vitalício, e o ciclo de 12 semanas | `tarifas.*`, `niveis.limiares`, `punicao.*`, `ciclo.*` |
| `ritos` | Ritos do dia | O loop diário: que rito, que hora, o que pede, o que grava | `ritos[]`, `tarifas.fechamento`, `tarifas.shutdown`, `tarifas.despejo` |
| `tarefas` | Tarefas e Triagem | Por que toda tarefa nasce em Staging e por que mover é ato seu (lei 3); o que acontece se o Staging envelhecer | `staging.dias_para_alerta`, `areas` |
| `leitura` | Leitura | A sessão: hooks por voz, compilar não publica, o portão do preview, de onde saem os cartões Anki | — |
| `guarda` | Onde tudo é salvo | Vault × SQLite × ClickUp × celular — e o que sobrevive se cada peça cair | — |

O **ciclo** não tem página própria: 12 semanas só faz sentido junto do que ele mede, então mora em
`pontos`.

**Diamante = nível.** Confirmado em `Revisao.tsx:68`: quatro losangos, os acesos são os N1–N4 já batidos, os
apagados os que faltam. "A caminho do N1" vem de `proximo_nivel.faltam` (`api.ts:369`). A página `pontos`
precisa dizer isso com essas palavras.

### 4.1 Regras de conteúdo

- **Tom:** segunda pessoa, presente, frase curta. *"Você joga a ideia fora da cabeça e segue. O worker
  classifica depois."* Nunca *"o sistema permite ao usuário registrar"*.
- **Tamanho:** teto de ~180 palavras por página. O aceite é responder as perguntas sozinho, não ler um manual.
  Página que não cabe virou duas.
- **Listas vivas:** `areas` e `ritos` são renderizados como lista a partir da resposta, não escritos à mão.
  Área nova no BFF aparece na wiki sem ninguém editar texto.
- **Fora:** rotas do BFF, nomes de arquivo, nomes de módulo. Isso é `AETERNUM-MAPA-DO-SISTEMA.md` §7–8, e é
  material de dev.

## 5. Navegação e portas de entrada

**Porta principal — ARQUIVO da Mesa.** Item novo em `mesaView.ts`, na lista `arquivo`, **incondicional**:

```
item("comofunciona", "Como funciona", "o sistema explicado")
```

Posição: **último do grupo, depois de `Ajustes`** — é referência, não trabalho parado; nunca deve competir com
os itens do ARQUIVO que representam filas.

**Portas contextuais** (as duas dúvidas nasceram nestas telas; obrigar a passar pela Mesa é fazer o Leo
procurar):

| Origem | Abre |
|---|---|
| Bloco de nível da Home (`Home.tsx:146`, o `—`/número que gerou a pergunta) | página `pontos` |
| Tela Capturar, junto do campo de captura rápida | página `captura` |

`openDestination` (`App.tsx:164`) passa a aceitar `comofunciona`, com slug de página opcional — as portas
contextuais abrem a página direto, sem passar pelo índice.

**Renomeações:** nenhuma. `Como funciona` é nome novo, usado igual nos três lugares (destino, item da Mesa,
`TITLES`). Não repete o defeito do B3 (Ritmos × Rotinas).

## 6. Falhas

A regra que o `mesaView.ts` já escreve em comentário — *"null nunca vira estado: sinal desconhecido manda o
item para o arquivo, sem número inventado"* — vale aqui inteira.

| Falha | Comportamento |
|---|---|
| Rota responde | Números renderizados, sem selo |
| Rota falha, existe cache | Números do cache + selo `valores de DD/mmm` no topo da página |
| Rota falha, sem cache | Cada slot vira `—` e a página mostra uma linha de aviso curta |
| Rota responde sem um campo | Só aquele slot vira `—`; os outros renderizam. Nunca `undefined` na tela, nunca página em branco |
| 401 / sem sessão | Cai no fluxo de login existente, igual a qualquer outra tela |
| Sem rede, sem cache | Idem "sem cache": o texto aparece inteiro (mora no bundle), só os números viram `—` |

**O texto nunca falha.** Está no bundle. A wiki abre sempre; o que pode faltar são os números, e quando faltam
ela diz.

**Cache:** chave própria no storage que o app já usa, gravada a cada resposta bem-sucedida, com o timestamp.
Não expira sozinho — expirar deixaria o Leo sem números offline, que é o pior momento. O selo de data é quem
resolve a honestidade.

## 7. Testes

Quatro, nenhum de fachada.

1. **Slot órfão** — `app/tests/wikiContent.test.mjs`. Varre todo `{...}` de todas as páginas e falha se o
   caminho não existir no fixture de contrato (§3.5). **É este teste que faz o aceite "mudar
   `pontos_por_rotina` muda a wiki" ser verdade e não promessa.**
2. **Horários** — `bff/tests/test_cron_horarios.py`. Lê `install-cron.ps1`, extrai `TaskName` × `-At HH:MM`,
   compara com `settings.ritos`. Ignora `Aeternum BFF`. Divergiu, quebra.
3. **Rota** — `bff/tests/test_wiki_parametros.py`. Exige auth (401 sem token); cada valor vem de `settings`,
   não de literal — o teste muda um setting e exige que a resposta mude junto; e o conjunto de caminhos da
   resposta bate exatamente com o fixture de contrato (§3.5).
4. **Mesa** — `app/tests/mesaView.test.mjs`. `comofunciona` entra em `TODOS_OS_DESTINOS` (11 → 12); as três
   asserções de ordem do ARQUIVO (linhas 117, 234, 249) ganham o item novo no fim.

**Correção ao que o B2 diz:** o backlog avisa que isto "muda a contagem de 11 destinos e o teste de 2160
combinações". As 2160 (`mesaView.test.mjs:86`) são `5 × 4 × 3 × 3 × 3 × 4`, o produto das **combinações de
sinais** — não têm relação com quantos destinos existem, e **continuam 2160**. O que muda é a lista de
destinos e as asserções de ordem. E como `Como funciona` entra no ARQUIVO incondicionalmente, o invariante
anti-órfão passa de graça: não há combinação em que ele suma.

## 8. Arquivos tocados

**Novos**

- `bff/tests/test_wiki_parametros.py`
- `bff/tests/test_cron_horarios.py`
- `app/src/wikiContent.ts`
- `app/src/screens/ComoFunciona.tsx`
- `app/tests/wikiContent.test.mjs`
- `app/tests/fixtures/wiki-parametros.json` — o contrato entre as duas linguagens (§3.5)

**Alterados**

- `bff/app/config.py` — campo `ritos`
- `bff/app/main.py` — rota `GET /wiki/parametros`
- `app/src/api.ts` — tipo + fetch dos parâmetros
- `app/src/mesaView.ts` — item no ARQUIVO
- `app/tests/mesaView.test.mjs` — destino novo + ordem
- `app/App.tsx` — `Tab`, `TITLES`, `openDestination`, render
- `app/src/screens/Home.tsx` — porta contextual no bloco de nível
- `app/src/screens/Capture.tsx` — porta contextual na captura rápida

## 9. Fora de escopo

- **`theme.ts:POINTS`** (D10). O app já é o segundo lugar que pode mentir: `theme.ts:73` tem
  `tarefa:10, rotina:20, captura:5, fechamento:80, shutdown:30, despejoBonus:40` hardcoded, hoje batendo com
  `config.py` por manutenção manual, e usado em Home, Capturar, Fechar e Mesa. Fica como está — é lido
  síncrono no render dessas quatro telas e trocar por fetch exige caminho de carregamento em todas. **Dívida
  registrada, fatia própria.**
- **Diagramas** (D8) — fatia 2.
- **Busca dentro da wiki** — não pedida; oito páginas cabem num índice.
- Qualquer mudança no pipeline de captura, na economia, ou em `/pontos`. A rota nova é read-only e não
  escreve em lugar nenhum.

## 10. Critério de aceite

Direto do B2, sem afrouxar:

1. O Leo abre `Como funciona` pela Mesa e responde **sozinho**, sem perguntar pra ninguém: o que é diamante,
   o que paga ponto e quanto, o que é o ciclo, e o que cada rito faz em que hora.
2. Mudar `pontos_por_rotina` na config **muda o texto da wiki**, sem ninguém editar a tela.
3. Tocar no bloco de nível da Home abre a página `pontos`; tocar na dica da Capturar abre a página `captura`.
4. Com o BFF desligado e sem cache, a wiki **abre**, o texto aparece inteiro, e os números aparecem como `—`
   com aviso. Com cache, aparecem com o selo de data.
5. `python -m pytest -q` e os testes `.mjs` do app passam, incluindo os quatro novos/alterados.

## 11. Fatias seguintes (não são deste spec)

| Fatia | O quê | Por que depois |
|---|---|---|
| 2 | Diagramas dos fluxos principais | Custo de layout real; o aceite do B2 não pede diagrama |
| 3 | `/wiki/parametros` (ou irmão) vira fonte de `theme.POINTS`, matando o hardcode | Encosta em 4 telas e nos testes; entrega própria |
| 4 | Links "o que é isso?" nas demais telas, agora que as páginas são endereçáveis | Aditivo, barato, mas só faz sentido com a fatia 1 no ar |
