---
artifact: auditoria
capability: escritorio
status: baseline
date: 2026-08-04
metodo: "teste empírico do app rodando (BFF+Expo+Hermes real+vault real) + 2 auditorias de código por domínio + consulta read-only ao data.db de produção"
escopo: "leitura, tarefas, cobrança, triagem, lembretes, agenda, diário/daily, notificações, agentes"
---

# AUDITORIA — Aeternum, agosto 2026

> Pergunta do Leo: *"teste todos os fluxos e veja se tá bom (eu acho que não tá tanto)."*
> Resposta curta: **você está certo, e a causa é mais estrutural do que acabamento.**

## Veredito

**O Aeternum é um sistema de REGISTRO excelente disfarçado de sistema de EXECUÇÃO.**

Tudo que *guarda* é de primeira: idempotência, fila retomável, "o buffer só limpa depois que o
vault confirma", lei 7 implementada de verdade, defesa contra prompt-injection em todos os
prompts. Isso é engenharia rara e não é elogio de cortesia.

Tudo que *age sobre você* está quebrado, ausente ou não confiável:

| Promessa | Registra? | Age? |
|---|:--:|---|
| Tarefas | ✅ vai pro ClickUp | ❌ **nunca é cobrada** — nasce sem prazo |
| Lembretes ⏰ | ✅ tabela, worker, TZ, deep-link | ❌ **0 linhas desde sempre** — nunca disparou |
| Notificações | ✅ push funciona | ❌ **~48% nunca chega** — depende do PC ligado |
| Rotinas | ✅ grava os checks | ❌ **o fechamento apaga o que você fez de manhã** |
| Mentor | ✅ UI bonita | ❌ **não sabe nada sobre você** |
| Shutdown 19h | ✅ mostra o que ficou aberto | ❌ **nada é clicável** |
| Triagem | ✅ propõe áreas | ❌ sem "descartar"; falha sem dizer por quê |

Não é falta de capricho. É que a metade "volante" do produto nunca foi ligada na metade "motor".

---

## A causa raiz: uma linha

Dois auditores independentes chegaram nela por caminhos diferentes, e ela foi verificada à mão.

```ts
// app/src/api.ts:178
export async function createTask(name: string, area: string) {
  ... body: JSON.stringify({ name, area })      // ← só isso
}
```

```python
# bff/app/main.py:360 — o BFF ACEITA, valida fail-closed, resolve TZ, agenda…
class CreateTaskIn(BaseModel):
    name: str; area: str; due: str | None = None; hora: str | None = None
```

O backend inteiro do prazo/lembrete está pronto e correto. **O app nunca envia.** Consequências:

1. Toda tarefa criada no app nasce sem `due` → `cadence.needs_nudge` devolve `False`
   (`cadence.py:57-72`) → cai no acordeão "SEM PRAZO" fechado → **nunca entra em digest nenhum.**
2. `POST /tasks` é o único caminho de usuário que chama `store.add_schedule` → a tabela
   `scheduler` tem **0 linhas em produção** depois de 3,5 semanas e 32 capturas. O
   `_scheduler_worker` roda a cada 60s há semanas **varrendo uma tabela vazia**.
3. Ficam órfãos: `fire_due_schedules`, `due_schedules`, `mark_schedule_fired`,
   `pending_schedules`, a fonte `hora_marcada` da agenda e o deep-link correspondente.

**Uma linha derruba a promessa central do produto** ("o sistema me cobra") e o recurso ⏰ inteiro.

---

## Crítico

### C1. O fechamento apaga o que você fez de manhã *(provado ao vivo)*
```
Marquei "yoga" na Abertura      → yoga: True,  +1 ponto
Fechei o dia sem re-marcar yoga → yoga: False  ← apagada silenciosamente
```
`/closing/routines` (`main.py:2253`) devolve só `id, slug, nome, bloco, passos` e **nunca lê
`routine_checks`**; a tela nasce em branco e o `record_checks` do `/closing/approve`
(`main.py:2291`) sobrescreve. **O padrão certo já existe 500 linhas acima**: `/abertura` faz
`checks = store.get_checks_on(data)` e devolve `feito` (`main.py:1732-1743`).

**A mitigação existente falha por 4 caminhos** (`Fechar.tsx:86-92` tenta semear de `getAbertura()`):
(a) `feitoManha` só traz `bloco == "manha"` — rotinas de dia/noite nunca têm estado prévio;
(b) se `getAbertura()` falhar, `feitoManha` fica `{}` e **tudo vira `false`**;
(c) escolher template diferente do da manhã **deleta** os checks anteriores (`store.py:1678-1686`)
antes do approve gravar `false` por cima — destruição dupla;
(d) o `??` só cai adiante em `null`; assim que um `false` entra, nunca mais consulta a manhã.

**Raio de destruição — 7 consumidores usam `routine_checks` como fonte única:**

| Consumidor | Onde | Efeito |
|---|---|---|
| Scorecard % | `tasks.py:201-221` | despenca — é o número do gate ≥85% |
| Pontos da semana | `pontos.py:76-93` | ganhos perdidos, **furos fabricados** |
| Padrão ≥3 furos → punição | `pontos.py:96-126` | **desconto por furos que não aconteceram** |
| Linha de cobrança do digest | `tasks.py:486-534` | `"🔁 yoga: 3 furos em 7d. −3 pts"` — cobrança falsa |
| Saldo + **nível vitalício** | `pontos.py:328-342` | `pico_total` perde o ganho → o nível "que não regride" **atrasa para sempre** |
| Objetivos acumulativos | `objetivos.py:44-57` | perde o dia no total, na semana e na série de 12 |
| Review semanal + mensal | `tasks.py:224-378` | os números do review somam dado corrompido |

**O rito que existe para provar que o loop engatou é o que destrói a prova.**

### C1.1 — A suíte de testes **certifica o bug** como comportamento correto
`bff/tests/test_dia.py:314-327` alimenta `True` na mão e comemora que o banco tem `1` — provando
apenas que `INSERT OR REPLACE` troca `1` por `1` — e chama isso de *"o caminho normal"*, quando o
app real **não tem como saber** que deve mandar `True`. Pior, `test_dia.py:330-339`
(*"o fechamento pode corrigir a marcação da manhã"*) **valida a destruição como feature**.

Nenhum teste exercita o caminho real tela → payload. Foi assim que *"código concluído · 348 testes
verdes"* foi declarado sobre um rito quebrado. O próprio P2-BACKLOG já avisava: *"contagem de
testes não prova cobertura de escopo."* Aconteceu de novo.

**A lição de processo é mais fina do que "faltou teste".** O docstring do
`test_fechamento_pode_corrigir_a_marcacao_da_manha` — *"o inverso também vale: se ele marcou
errado de manhã, a tela das 21h corrige"* — mostra que a destruição foi **racionalizada como
feature**, não deixada de fora por descuido. Alguém olhou para o comportamento, construiu uma
justificativa plausível ("é a correção do dia") e a congelou num teste. Foi essa racionalização,
e não a ausência de cobertura, que blindou o bug. **O antídoto não é escrever mais testes: é
exigir que o teste monte o payload a partir da resposta real do servidor**, em vez de digitar à
mão o valor que torna a asserção verdadeira.

### C1.2 — O incentivo aponta para **NÃO** fechar o dia
`pontos.py:24-27` decide (corretamente, pela lei 4) que **linha ausente não é furo**. Mas
`Fechar.tsx:129-133` grava `false` para tudo que não foi tocado. Logo:

| Comportamento | Ganho | Furo | Scorecard |
|---|---|---|---|
| Dia bom, fechado | +N | 0 | sobe |
| **Dia ruim, fechado (honesto)** | 0 | **+3 → padrão → −3 pts** | **desce** |
| **Dia ruim, ignorado** | 0 | **0** | **intacto** |

**Registrar honestamente é a única forma de gerar furo; abandonar o app sai de graça.** O `≥85%`
mede *"dos dias em que me dei ao trabalho de registrar, quantos fui bem"* — auto-elogioso por
construção. É o oposto exato do critério de sucesso da SPEC §11.

### C1.3 — MODO RETORNO não existe. Zero linhas.
`grep -ri "modo retorno|voltar hoje|dias_ausente"` → nada. Não há sequer detecção de ausência.
Quem some 10 dias volta e recebe o digest inteiro em 🚨, o "Foco de hoje" lotado de atrasadas e o
rito da hora como se nada tivesse acontecido — **exatamente a pilha de culpa que a lei 4 proíbe**,
no momento em que ela mais machuca. Para um sistema desenhado para TDAH, é a diferença entre
voltar e desinstalar.

### C2. Tarefa criada no app nunca é cobrada
Ver "causa raiz". `app/src/screens/Tasks.tsx:194-212` — o painel "Nova ação" não tem campo de data.

### C3. O ⏰ nunca funcionou. Nem uma vez.
`SELECT COUNT(*) FROM scheduler` em produção → **0**. Mesma causa raiz.

### C4. Não existe adiar/reagendar/editar
Não há `PATCH /tasks` — só `POST /tasks` e `POST /tasks/{id}/complete` (verificado). O
`TaskDetailModal` oferece "Concluir / Abrir no ClickUp / Fechar".

**Impacto:** tarefa atrasada 9 dias que você decidiu fazer semana que vem tem três saídas:
concluir mentindo (polui pontos e review), sair pro ClickUp (o "cemitério" que a lei 5 proíbe),
ou aguentar 🚨 todo dia — que é o que **treina você a ignorar o digest**. A lei 4 exige
"replanejar, não envergonhar". **Cobrança sem botão de adiar não é cobrança, é ruído.**

### C5. O Mentor não sabe nada — nem de você, nem da conversa
```python
# hermes_client.py:357
async def chat(text, mode):
    return await _oneshot(f"{MODE_FRAME.get(mode,'')}\n\n{text}")   # persona + texto. Só.
```
Confirmado ao vivo: *"o que merece meu foco agora?"* com 4 tarefas atrasadas → 46s → resposta
genérica de coach, sem citar nenhuma. E **não há histórico**: `ChatIn` é `{text, mode}`
(`main.py:332`), cada mensagem é um subprocesso novo, e `App.tsx:330` desmonta o Chat ao trocar
de aba — **o padrão para preservar existe 5 linhas acima**, aplicado ao Capture (`App.tsx:319-325`).

**Impacto:** a superfície de IA mais visível entrega menos que o ChatGPT no navegador, onde ao
menos há histórico. É provavelmente a origem direta da sensação de "não tá tão bom".

### C6. O token expira em 30 dias e trava o app sem saída
TTL 720h (`config.py:23`). Nenhum helper de `api.ts` trata 401. Pior: o logout
(`Settings.tsx:53-66`) chama `unregisterDevice` **antes** de `clearToken()` — com token expirado
o `unregisterDevice` dá 401, lança, e **o `clearToken()` nunca executa**. Só se manifesta com
push token registrado, ou seja, **exatamente no dev build**. Saída única: limpar dados pelo Android.

---

## Alto

- **A1. ~48% das notificações nunca acontecem.** `notif_log` de produção, 10/jul→04/ago,
  esperado ~6/dia: **9 dias com ZERO** (14, 19, 21, 23, 25, 26, 28, 29, 31 de julho); 84 entregas
  onde caberiam ~160. O gatilho é Windows Task Scheduler no seu PC — **o canal tem o uptime do
  seu desktop**, e o que se perde não é replayado nem registrado.
- **A2. A Home dispara um LLM a cada abertura e sempre estoura o próprio timeout.**
  `/triagem` → `propose_triage`, cujo único curto-circuito é `if settings.hermes_mock`
  (`hermes_client.py:188`). Com Hermes real e **lista vazia**, monta o prompt e chama o LLM:
  **8,58s medidos** contra timeout de 6s (`Home.tsx:64`) → banner *"alguns dados não responderam"*
  em **toda** carga. Agravantes: o `Promise.race` não cancela o servidor (subprocesso órfão), a
  Home recarrega a cada foreground **e a cada toque em notificação**, e não há semáforo entre os
  7 call sites do Hermes.
- **A3. Abrir a Home custa ~30 chamadas ao ClickUp.** `/digest`, `/abertura` e `/triagem` fazem
  10 GETs sequenciais cada (`tasks.py:570`, `clickup_client.py:141`). Com token pessoal
  (~100 req/min), dois foregrounds seguidos raspam o teto → 429.
- **A4. Captura com prazo fica presa no Staging e não é cobrada.** `tasks.py:575` exclui o
  Staging inteiro do digest. "pagar o Inter dia 5" capturado dia 2 vence dia 5 e **o digest cala**.
  O caminho padrão da captura desemboca num ponto cego do motor de cobrança.
- **A5. O rito mais importante tem a pior tela.** Abertura = cards e checkboxes reais.
  Fechar o dia = glifos `☐` de texto, sem cards, alvo de toque minúsculo, e dois links
  ("estruturar com o Hermes" / "gravar direto") sem botão primário.
- **A6. O Shutdown das 19h é um painel morto.** `Shutdown.tsx:183-192` — as linhas são `View`,
  nada clicável; e o contador de staging manda "triar no ClickUp" **apesar de a tela Triagem
  existir no app** sem nenhum caminho até ela.
- **A7. Ticket do Expo ≠ entrega.** `notify.py:32-50` decide "entregou" pelo ticket; não há
  tratamento de receipts. Token morto → ticket `ok` → a ponte Telegram nunca sobe, o aviso some,
  e **o `notif_log` registra sucesso**. O log mente.
- **A8. 46s sem streaming, sem cancelar.** Sem `AbortController` em `chatSend`; o servidor
  permite até 150s. E o erro aparece **na voz do Mentor**: `Chat.tsx:281` renderiza a exception
  como fala do agente → *"o Mentor diz: erro 502"*.
- **A9. `move_task` não é atômico.** GET → add → DELETE sem compensação, retornando `True`
  incondicionalmente (`clickup_client.py:206-233`); `fetch_open` não deduplica por id → a tarefa
  aparece **duas vezes** na tela e no digest, e a triagem reporta `ok`.
- **A11. A tela de Triagem é praticamente inalcançável.** Porta **única** no app inteiro
  (`Home.tsx:249`), condicionada a `staging > 0` — que vem de `getTriagem()`, que estoura o
  timeout de 6s (A2) → `signals.staging` fica `null` → **o badge não renderiza e a tela some**.
  Não está na grade "Ferramentas", que tem espaço de sobra. O item 13 do P2 ("código concluído")
  é invisível na maior parte das sessões.
- **A12. A Revisão é um dashboard, não um rito — e não produz artefato nenhum.** Nada vai pro
  vault (a SPEC A4 exige `Fechamentos/Weekly/YYYY-WW.md` aprovado), **não existe tabela de review**
  → o sistema não sabe se o review aconteceu → *"2 semanas puladas → Mentor"* é matematicamente
  impossível. O balanço patrimonial mensal é uma **string fixa** (`tasks.py:375-377`).
- **A13. O "Mentor com voz" não existe no backend.** Nenhum gatilho: nem 3 furos, nem scorecard
  <85%, nem review pulado, nem pendência >7d. A escalada inteira colapsa numa linha de texto no
  digest. O P2 item 3 prometeu, como condição de aceite da punição, *"o Mentor dizendo o motivo —
  não um placar mudo"*. Entregue: **um placar mudo.**
- **A14. Inserir no Google Calendar não aparece na agenda.** Escrita via Calendar API; leitura via
  **ICS público com cache de 15 min** (que o Google atualiza em horas). Os dois caminhos não se
  falam; o evento injetado no estado local some ao primeiro refresh → você acha que falhou e
  insere de novo. E não existe superfície de calendário: `GET /agenda` está implementado e
  **nenhuma tela o chama** — não dá pra ver amanhã nem a semana.
- **A15. Staleness é código morto.** `update_offset=None` sempre (`tasks.py:145`), então o ramo
  "parada há N dias" (`cadence.py:69-71`) nunca executa. **Delegação sem data nunca é cobrada por
  nada** — mas o rótulo "parada há Xd" aparece no mock, dando falsa impressão em dev.

## Médio

- **M1.** `count` e `tasks` do `/digest` divergem depois das 9h (`main.py:1447-1459`): conclua às
  10h e o badge continua "3" com dois itens na tela. Num sistema de "número frio", número errado
  corrói o mecanismo.
- **M2.** Não há fila offline para tarefas — concluir no metrô evapora (`Tasks.tsx:135-138`);
  `captureQueue` cobre só captura e sessão.
- **M3.** Confirmação de conclusão renderiza **no topo do scroll**: tocar no check de um item lá
  embaixo não dá feedback nenhum. É a ação primária da tela.
- **M4.** Fusos ingênuos no caminho da cobrança (`clickup_client.py:67-72`, `tasks.py:588`,
  `store.py:1403`) — **no VPS UTC, depois das 21h BRT todo `days_overdue` desloca um dia.**
- **M5.** Schedule que não entrega **nunca para de tentar** (a cada 60s, para sempre); e assim que
  dispara some dos follow-ups do Shutdown mesmo sem ter sido resolvido (`main.py:89-95`).
- **M6.** Retry da fila queima 5 tentativas em 25s sem backoff; de `failed` só volta com restart
  do BFF (`store.py:22`, `main.py:72`).
- **M7.** Horário dos ritos duplicado em 3 fontes que **já divergem** (texto em `main.py:39-46`,
  gatilho no `install-cron.ps1`, decisão do card em `homeAction.ts:97-115`) — e "rotinas
  editáveis" não alcança nenhuma das três.
- **M8.** Triagem não oferece "morte digna" (só mover para uma área de vida) e a falha é opaca:
  *"0 movidas · 20 não movidas"* sem dizer quais nem por quê.
- **M9.** "Ferramentas" na Home é uma gaveta de 8 botões sem hierarquia nem badge de "precisa de
  você agora"; a barra de captura cobre a 3ª tarefa do Foco.
- **M10.** Cada captura varre o histórico inteiro do Staging com `include_closed=True`
  (`capture_pipeline.py:121`) — custo cresce para sempre.
- **M11.** **A "prática da semana" nunca expira** (`store.py:1973-1987`): `pratica_semana` é
  gravado e nunca comparado. Uma prática escolhida em 12/jul continua sendo anunciada como
  "prática da SEMANA" em agosto, nunca pergunta "aplicou?" e nunca entra no scorecard. É a dor
  original — *"aprendo hacks e esqueço de aplicar"* — com UI por cima.
- **M12.** **Não dá pra marcar as rotinas sem escrever o diário**: os dois botões do fechamento,
  inclusive o "modo mínimo", exigem `dump.trim()` (`Fechar.tsx:160`). A manhã tem check por toque;
  a noite não. Essa assimetria **produz** os dias sem registro do C1.2.
- **M13.** **Nível 0 por ~3 meses.** Com a semente (≈61 pts/semana **perfeita**), N1 = 700 pts ≈
  11,5 semanas de aderência 100% — um ciclo 12WY inteiro em N0. E esse `0` é o selo de destaque da
  Home, o único elemento gamificado do app.
- **M14.** Fim do rito devolve só `"✓ dia fechado"` — sem pontos, sem scorecard, sem navegação.
  Para um design que declara "check visível (dopamina)" como lei, o momento mais importante do dia
  não devolve nada.
- **M15.** `dailies` pode passar de 7/7 (`main.py:2284`): o `log_event` roda mesmo quando o dedupe
  impediu a escrita → `"dailies 8/7"` no review.
- **M16.** ⏰ é cobrado 2× (digest das 9h + disparo na hora, sem dedupe — `tasks.py:588` vs
  `main.py:84-96`).

---

## O que está genuinamente bom

Isto não é consolo: é a razão pela qual tudo acima é consertável em vez de fatal.

- **`cadence.py`** — puro, determinístico, sem I/O, tabela única de limiares. O front só exibe.
  A peça mais bem-feita do sistema.
- **A lei 7 está implementada de verdade.** `_norm` com NFKD+fold para não vazar por drift de
  acento; `eh_sensivel` ponto único; o corpo do push usa o mesmo texto neutralizado do Telegram.
  Auditamos todos os `logger.*` do BFF: **nenhum vazamento**. O bot token na URL do Telegram não
  vaza porque só se loga `type(e).__name__`.
- **Defesa contra prompt-injection em todos os prompts** com dado do usuário (`<captura>`,
  `<staging>`, `<notas>`, `<sessao>`), cada um com instrução explícita de não obedecer o conteúdo.
- **`notify.py` fechou de verdade o órfão do canal.** A denúncia antiga ("push existe e ninguém
  chama; 100% Telegram") **está morta**: 73 entregas por push, zero Telegram desde 12/jul.
- **Triagem respeita a lei 3 com rigor incomum**: sugestão nunca equivale a aprovação, e o BFF
  reconfere a pertinência ao Staging imediatamente antes de mover.
- **`capture_pipeline`** — idempotência por coluna + marker `[cap:N]` + UNIQUE: retomável após
  crash sem duplicar.
- **Staging da leitura** (entregue nesta sessão) e o diário gravando no vault com raw + wiki-link.
- **Fail-closed nas fronteiras do ClickUp**: recusa tarefas fora das listas do Aeternum.

---

## Plano

### ⚠️ Antes de qualquer coisa: o histórico está contaminado

Os `routine_checks` gravados desde que o fechamento das 21h entrou em uso carregam `false` falsos.
Rodar `SELECT data, rotina, feito FROM routine_checks ORDER BY data` e decidir: o histórico é
recuperável, ou é melhor zerar a âncora do ciclo (`ciclo_inicio` em `config.py`) e recomeçar com
dado limpo? **Não vale calibrar punição em cima do banco atual** — e enquanto o C1 não for
corrigido, cada fechamento adiciona mais lixo.

### As 5 linhas que consertam mais (fazer primeiro)

| # | Onde | Mudança | Mata |
|---|---|---|---|
| 1 | `hermes_client.py:190` | `if not itens: return []` | banner de erro permanente da Home |
| 2 | `main.py:2253` | `/closing/routines` devolve `feito` via `get_checks_on` (padrão já existe em `main.py:1732`) | C1 — corrupção de dados |
| 3 | `api.ts:178` + `Tasks.tsx` | campo de prazo/hora e enviar `due`/`hora` | C2 **e** C3 — cobrança e ⏰ |
| 4 | `main.py:1450` | `count = len(fresh["tasks"])` | M1 — badge mentindo |
| 5 | `tasks.py` `fetch_open` | dedupe por `id` | A9 — tarefa duplicada |

> **Sequência sugerida para a primeira tarde:** #2 (servidor devolve `feito`) → **reescrever os
> testes que certificam o bug** → tri-estado no `Fechar.tsx` (nunca enviar `false` para rotina
> não-tocada; mata C1.2 sem tocar em `pontos.py`) → `date.today()` → `hoje_local()` nas rotas de
> rito. Ao fim disso o dado volta a ser confiável — que é pré-requisito de todo o resto.

### Semana 1 (S)
Logout: `clearToken()` **antes** do `unregisterDevice` + wrapper 401 → tela de login (C6) ·
tirar `getTriagem` do load da Home (A2) · cache TTL 60s em `fetch_open` (A3) · linhas do Shutdown
tocáveis abrindo o `TaskDetailModal` que já existe (A6) · confirmação de conclusão dentro da linha
ou otimista com "desfazer" (M3) · TZ explícito antes do VPS (M4) · `asyncio.Semaphore(1)` no
`_oneshot` · corte de obsolescência no scheduler (M5).

### O que muda o produto (M)
1. **Contexto no Mentor** — injetar bloco compacto de estado (atrasadas, pontos, rotinas em
   padrão, prioridade nº1). Tudo já existe em `run_digest`/`pontos.resumo`. **É o que separa "um
   LLM genérico" do "Mentor do Leo".**
2. **Histórico no Chat** — `mountedScreen` como no Capture + `history` no `ChatIn`.
3. **Botão Adiar** (`PATCH /tasks/{id}`) — fecha a lei 4 e desarma o incentivo a concluir mentindo.
4. **Redesenhar "Fechar o dia"** no padrão da Abertura.
5. **Card "Canal" nas Ajustes** (`GET /notif/status`) — sem isso, a perda de 48% continua invisível.
6. **Tirar o gatilho do PC** (VPS) — é a única correção real para A1.

---

## Método e limites

Ambiente isolado: banco temporário, ClickUp em **mock** (nada foi criado no ClickUp real), branch
descartável do vault (criada e deletada), segredos descartáveis. Consultas ao `data.db` de
produção foram **somente leitura**. Nada foi modificado; nenhum segredo foi impresso.

**Não coberto:** a integração real com o ClickUp (rodou em mock) e o app em Android físico (o
teste de UI foi no build web, então gestos, teclado, permissões e o comportamento real do push no
aparelho não foram exercitados).

**Fontes:** teste empírico direto (UI + API + vault + banco) mais três auditorias de código por
domínio — tarefas/cobrança/triagem/ClickUp, ritos/reflexão/agenda, e canal/notificações/agentes.
Os achados que aparecem aqui como críticos foram confirmados por pelo menos duas fontes
independentes, e os dois mais graves (C1 e C2/C3) foram reproduzidos à mão contra o sistema rodando.
