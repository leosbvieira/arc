---
artifact: workflow-catalog
capability: aeternum
status: v1-draft
date: 2026-07-06
revision: incorpora 2ª–6ª rodadas (staging profissional+triagem no ClickUp, motor unificado, Anki AnkiConnect+template Frente/Meaning/Example/Hook+decks por domínio, app-first, chats por área, check-in 5h30+8h20 c/ dois templates de dia, review dom 20h + mensal fundido + balanço mensal, ciclo 12WY, #24 kaizen, lane batch, sqlite local, B7 áudio contínuo, Edificação, Manual/SOP, objetivos acumulativos, punição por pontos, calendários Outlook+GCal — 6ª rodada trava todas as pendências)
source_of_truth: AETERNUM-DESIGN-INPUTS.md   # em conflito, o INPUTS manda
scope: conceitual (o QUE e o PORQUÊ dos workflows), não implementação
---

# AETERNUM — CATÁLOGO DE WORKFLOWS v1

Catálogo dos 24 workflows do esqueleto v0 (seção 9 do INPUTS + #24 kaizen da 4ª rodada), para o Leo ler, selecionar e
discutir a fundo. Cada workflow segue um formato fixo: **Objetivo · Gatilho · Sub-fluxo ·
Notificações · Hoje vs falta · Decisões abertas**. Tom direto, conceitual — não é a spec.

Regras que atravessam TODO o catálogo (as 9 leis do INPUTS, resumidas):
**vazão antes de captura · captura nunca exige decisão · a IA nunca grava no vault sem aprovar ·
leis TDAH (campo fixo, gatilho por evento, check visível, jamais streak punitivo, time-boxing,
IA como body double) · contra o cemitério de planilhas · cobrança por número frio, não por humor ·
privacidade em notificação · glass, not store · senhas ficam fora.**

**Prioridade de discussão (confirmada pelo Leo):** aprofundar primeiro **#6 captura → #3 fechamento
noturno → #10-11 motor de cobranças + escalada** — são os três que recebem o máximo de detalhe aqui.

### Status das decisões — 5ª/6ª rodada (2026-07-09, final)
**TRAVADO** = fechado pelo Leo · **ACEITO** = recomendação aprovada · **PENDENTE** = recomendado, aguarda confirmação · **NOVO** = feature nova desta rodada.

| Item | Status | Resumo |
|---|---|---|
| A1.1 estado perguntado · A1.2 tela de alarme · A1a vibra no Garmin | TRAVADO | 8h20 pergunta o estado; 5h30 é tela de alarme; Garmin vibra |
| Dois templates de dia (Yoga / Corrida) | TRAVADO | corrida sempre DEPOIS da academia; jornal 8h30 |
| A2 nome = "Shutdown" · janelas+varredura 19h · dois ritos | TRAVADO | — |
| Triagem do staging **no ClickUp** (app não tem UI; Shutdown mostra "staging: N") | TRAVADO | afeta A2/B6/D14 |
| A4 temas da semana + agenda do dia no check-in (A1b) | NOVO | evento dia+hora lembra na hora |
| A5 balanço patrimonial **mensal** (1º domingo) | TRAVADO | — |
| B6 captura pelo app primária · hora-própria via scheduler D18 · cheatsheet | TRAVADO/NOVO | — |
| B7 **áudio contínuo** + hooks falados + sessão cronometrada · B7.1 buffer local+autosave BFF | TRAVADO | redesenho da leitura |
| B8.2 card = Frente/Meaning/Example/Hook | TRAVADO | decks por domínio = PENDENTE |
| B9 Edificação (aprender→aplicar) | NOVO | atravessa B9/A4/E20 |
| Manual/SOP no app (tooltips + diagramas) | NOVO | transversal, ver F |
| Objetivos acumulativos (dashboard de aderência, publicável no GitHub) | NOVO | D19/C12 |
| D16.1 recriar recorrências à mão (planilha = referência) | TRAVADO | — |
| Áreas: seguir com as 8 do Leo | ACEITO | mapa-de-vida × listas operacionais em aberto |
| C10.1-3 · C11.1-3 · C12 · C13 · C24 · D15 · D17 · D18 · D19 · D23 · E20 · E21 · E22 | ACEITO | recomendações aprovadas |
| A3.1 scorecard (sqlite+visão) · A3.3 punição por pontos · A4.2 Rerise gated ≥85% · A4.3 graduar no app · A5.2 12WY (ciclo) · decks Anki por domínio | TRAVADO (6ª) | todas as pendências da 5ª aprovadas pelo Leo |
| Calendários: Outlook (IA só lê) + Google Calendar (IA lê e insere) · superfície de Calendário no app | TRAVADO/NOVO (6ª) | agenda agregada; ver F, A1b, A4, D18 |

**Sem pendências (6ª rodada, final):** todas as decisões estão TRAVADAS ou ACEITAS.

---

## 1. Visão de 1 página

### O loop central

```
        ┌─────────────────────────────────────────────────────────────┐
        │                                                             │
   CAPTURAR ──► TRIAR ──► EXECUTAR ──► SER COBRADO ──► REFLETIR ──► PLANEJAR
   (1 campo)   (IA       (tarefa/     (digest +      (IA fecha    (dia→sem→
    voz/txt    estrutura, sessão/     escalada de    o loop, Leo   mês→...→10a
    B6/B7)     Leo        rotina)     tom, número    aprova)       A1-A5,W19)
               aprova)    C10/C11     frio)          A3/W12
        │                                                             │
        └──────────────  o SISTEMA é o único lugar  ──────────────────┘
```

A dor nº1 do Leo é **vazão + disciplina**: ele já captura (WhatsApp consigo, 99 abas, bloco de
notas) e parou porque **nada reaparece**. O loop só engata se todo capturado tiver destino,
reapresentação ou morte digna — e se a cobrança e a reflexão acontecerem **por ele** (a IA fecha o
loop; ele nunca reconstrói estrutura). Tudo o que segue serve esse loop.

### O dia-alvo como timeline (onde cada rito/workflow encaixa)

| Hora | Bloco do dia | Workflow(s) que encaixam | Superfície |
|---|---|---|---|
| **5h30** | acordar → **A1a toque** (alarme/checklist anti-doomscroll, guia a sequência) | **A1a** — dois templates de dia (ver A1) | app + Garmin (vibra) |
| DIA YOGA | yoga → meditação → rotinas (skincare) → academia 1h → escritório ~8h | rotinas binárias (scorecard A3) + W23 | app/Garmin |
| DIA CORRIDA | rotinas → **academia adiantada** → **corrida 30min (SEMPRE depois da academia)** → escritório ~8h30 | rotinas + W23 (corrida = sessão) | Garmin (timer) |
| ~8h/8h30 | chega ao escritório | **A1b check-in na mesa** (agenda do dia c/ horários, dia planejado, prioridade #1, marca rotinas) | app (cockpit) |
| ~8h30 | jornal 30min | captura solta (B6) do que aparece | app |
| ~9h00 | organizar cobranças do dia 30min | **C10 digest** (o sistema cobra o Leo) | app (Revisão) |
| 9h30 | daily ITER | — (fora do escopo pessoal) | — |
| janelas do dia | triagem do staging de trabalho (migrar p/ listas finais) | **W6/W14** triagem assistida por IA; follow-up de prazo curto lembra NA HORA (W18) | app |
| manhã/tarde | blocos deep/shallow/reuniões | **C11** timers de bloco + W23 + interstitial opcional | Garmin + app |
| ~13h | almoço 30min na mesa | — | — |
| **19h** | **rito de encerramento do trabalho** (30-60min) | **A2** (shutdown ITER, W18 follow-ups, plano de amanhã) | app (cockpit) |
| noite | casa: estudo/projeto OU pessoal | W23 (sessão foco) · W7 (leitura) · W8 (Anki) · W15 (saúde) | app/Telegram/Garmin |
| ~21h | fechamento noturno | **A3** (diário→IA→aprova, 1 destaque ressurgido, scorecard) | app (cockpit) |
| 21h30 | deitar → ler até 22h30 | W7 (sessão de leitura noturna) | app/Telegram |
| dom 20h30 | sincronização Anki | **C13** (AnkiConnect quando o Anki abre) | app + Anki |
| **dom 20h** (travado) | review semanal | **A4** (scorecard %, esvaziar inbox de ideias W17) | app (cockpit) |
| **1º domingo do mês, 20h** | review mensal FUNDIDO ao semanal (sessão estendida, 1 rito) | **A5** (mensal→trim→anual) | app + vault |
| FDS / madrugada | jardinar o vault, dashboard, sugerir links/Anki | **batch**: `claude`+`codex` CLI no PC (C12/C24) | PC (batch) |

Nota: review semanal **travado em dom 20h** (3ª rodada); mensal = **1º domingo, fundido ao semanal**. O comando do vault (dom 22h) será corrigido na implementação.

### O mapa de dados — o que mora onde (lei nº8: glass, not store)

| Onde | O que mora | Papel |
|---|---|---|
| **ClickUp** (hoje 4 listas: Trabalho/Finanças/Saúde/Pessoal; estrutura final — spec §8: **10 listas = Staging + Trabalho (ITER) + as 8 áreas de vida**, Aguardando = tag transversal — ver W14) | TODAS as tarefas, due dates, recência, obrigações financeiras recorrentes, follow-ups/aguardando, tarefas de saúde (marcar médico), tarefas de trabalho em staging | **home canônica de tarefas** — a única |
| **Vault** (Obsidian em GitHub, `LeonardoLifeMain`) | conhecimento, reflexão, diário, identidade, leituras, ideias (quarentena), fechamentos daily/weekly/monthly, Conquistas N1-4, SOPs, hierarquia de planos (10a→dia), cards Anki `pending`, terapia | **home canônica de conhecimento/reflexão** |
| **Hermes memory** | memória do agente, contexto conversacional, personalidades (tarefas/capturas/mentor/conselho), estado aprendido | **memória do assistente** |
| **Anki** | flashcards, repetição espaçada | **dono da retenção dura** |
| **Garmin** | alarmes de rito, timers de bloco | **satélite** (não app completo) |
| **Calendários** (Outlook prof. · Google Calendar pessoal) | eventos/compromissos com dia+hora | **fonte externa**: Outlook = IA **só lê** (read-only best-effort); GCal = IA **lê e insere** (com aprovação, lei nº3). Nada canônico no app |
| **App (Expo)** + **BFF sqlite** | NADA canônico — só auth/sessão + device tokens de push (scaffolding). **App-first: superfície primária, inclusive de notificação** | **vidro** sobre o Hermes |

Regra de ouro: se um workflow precisar "guardar" algo novo, ele mora numa dessas homes existentes.
Persistência nova no BFF só é permitida para *estado de scaffolding* (dedupe, cache), nunca conteúdo.

**Regra de persistência (3ª/4ª rodada): sem SQL em nuvem.** Se o **Leo lê** → vault (markdown/dataview)
ou ClickUp. Se **só a máquina lê** (telemetria, device tokens, checks de rotina, sessões, log de
notificação) → **sqlite local** (hoje no PC do Leo, depois no VPS). SQL gerenciado em nuvem só faria
sentido com múltiplos dispositivos escrevendo offline — não é o caso (single-user, glass-not-store).

### Duas lanes de modelo (compute, não dado)
- **Hermes (interativo, diário)** — captura, chat, cobrança, ritos. É o engine sempre-ligado.
- **Batch pesado (`claude` CLI + `codex` CLI, OAuth das assinaturas, RODANDO NO PC do Leo)** —
  trabalhos de fim de semana/madrugada: jardinar o vault, sugerir links e candidatos a Anki, gerar
  o dashboard (C12), rodar o agente de melhoria (C24). Compatível com a regra "só binários oficiais
  usam OAuth, em batch, na máquina dele". É uma lane de cron própria, separada do interativo.

---

## 2. Os workflows

Convenção: cada passo cita a **superfície** (app / Telegram / Garmin / Obsidian / automático) e o
fluxo de dados **origem → transformação → destino**. "Hoje" = o que o as-built já faz; "falta" = o
que precisa nascer.

---

## A — Ritos (a espinha do dia)

### A1 · Check-in matinal
**Objetivo:** dar ao Leo um "brief" de 3-5 min que define o dia sem exigir que ele monte nada (contra a página em branco).

**Gatilho:** DUAS interações (opção b, 3ª rodada) — **(a)** toque às **5h30 ao acordar** e **(b)** check-in às **8h20 na mesa**. O toque das 5h30 é formato alarme/checklist (anti-doomscroll), não feed.

**Sub-fluxo:**
1. **(a) 5h30 — toque ao acordar (travado 5ª rodada):** o app guia a sequência por **um de dois templates** — **DIA YOGA** (yoga → meditação → rotinas → academia → escritório ~8h) ou **DIA CORRIDA** (sem yoga/meditação; **academia adiantada**; **corrida 30min sempre DEPOIS da academia** → escritório ~8h30; jornal 8h30). Formato **alarme/checklist**, sem feed nem decisão (anti-doomscroll). Origem: template do dia (editável) → **app** (+ **vibra no Garmin**, futuro mini-app de alarmes). Marca as rotinas no scorecard ao concluir.
2. **(b) 8h20 — check-in na mesa:** **3 prompts fixos** (foco do dia · estado energia/clareza · a coisa que não pode furar) **+ RESUMO DA AGENDA DO DIA com horários** — agrega **Outlook** (read-only) + **Google Calendar** + itens de hora marcada (D18/B6) + ritos, pela superfície de **Calendário** (F). Campo fixo, nunca em branco (lei TDAH). — superfície: **app** (cockpit).
3. O sistema puxa as **3 Prioridades** do dia: tarefas que vencem hoje + o "piso mínimo" das rotinas. Origem: **ClickUp** (due=hoje) → seleção → **Home** do app. Leo confirma/reordena (1 toque cada); nada é gravado no vault aqui.
4. O estado declarado alimenta o enquadramento do dia ("energia baixa · clareza alta" na Home) e fica disponível pro fechamento noturno (A3) comparar intenção × realizado.

**Notificações:** empurrão seco às 5h30 (alarme) e um lembrete leve se o check-in de 8h20 não veio até 9h. Sem conteúdo sensível no preview (lei nº7). Se o Leo pulou o check-in por 3 dias, o Mentor (C11) comenta — não o nudge frio.

**Hoje vs falta:**
- **Hoje:** a Home existe (v2 "brief da noite"), mas energia/clareza são **hardcoded**; as 3 Prioridades não vêm do digest real; não há toque das 5h30.
- **Falta:** as **duas interações** (5h30 guia-sequência + 8h20 check-in); os 3 prompts como fluxo; ligar estado → Home; puxar prioridades do ClickUp; marcar rotinas no scorecard (persistido em **sqlite local** — só a máquina lê).

**Decisões abertas:**
1. *(TRAVADO 5ª rodada — A1.1: estado **PERGUNTADO** no check-in de 8h20, 1 toque em escala, não inferido.)*
2. *(TRAVADO 5ª rodada — A1.2: o toque das 5h30 é uma **tela simples de alarme/checklist** dedicada, não a Home com feed. **Vibra no Garmin** — futuro mini-app Garmin de alarmes.)*
3. *(TRAVADO 6ª rodada — fonte da agenda: **Outlook** profissional (IA **só lê**, read-only best-effort) + **Google Calendar** pessoal (IA **lê e insere**, com aprovação). O app ganha superfície de **Calendário** — ver F.)*

---

### A2 · Shutdown — encerramento do trabalho (19h)
**Objetivo:** separar o "founder que executa" do "planejador que fecha" — shutdown do ITER + preparar amanhã, para a noite pessoal começar limpa (planner ≠ executioner).

**Gatilho:** hora marcada (19h) com piso mínimo; idealmente encadeado a um evento ("quando fecho o laptop do trabalho").

**Sub-fluxo:**
1. Às 19h, o app abre o rito com checklist fixo: pendências do dia, follow-ups a cobrar (W18), o que fica pra amanhã. — superfície: **app** (Telegram só na transição).
2. **Triagem do staging acontece NO ClickUp (travado 5ª rodada):** a IA salva a captura de trabalho na lista **staging**; o Leo promove/triata **dentro do próprio ClickUp** quando quiser (um agente IA pode ajudar em lote). O app **não constrói UI de triagem** — no máximo o Shutdown mostra **"staging: N itens"** como lembrete de varrer. Itens de prazo curto que já venceram no dia não entram aqui (cobrados na hora, W18).
3. Leo varre as tarefas de **Trabalho** do dia: fecha o que fez, empurra o que não fez. Origem: **ClickUp** → toques de complete/reschedule → **ClickUp**.
4. **Plano de amanhã:** o sistema propõe as 3 prioridades de amanhã (tarefas que vencem + rotinas), Leo aprova/edita. Isso pré-carrega o A1 do dia seguinte. Destino: estado leve (não é vault).
5. Follow-ups/delegações que ficaram esperando resposta entram/atualizam a lista **Aguardando** (W18).

**Notificações:** empurrão às 19h ("hora de fechar o dia de trabalho"). Se o rito for pulado, reaparece amanhã, mais firme (C11), nunca envergonhando.

**Hoje vs falta:**
- **Hoje:** nada — não existe rito das 19h no as-built.
- **Falta:** o checklist, o "plano de amanhã" que pré-carrega o A1, a costura com W18, e o contador **"staging: N itens"** no Shutdown (a triagem em si é no ClickUp, W14).

**Decisões abertas:**
1. *(TRAVADO 5ª rodada — nome = **"Shutdown"**.)*
2. *(TRAVADO 5ª rodada — A2.2: 1-2 janelas de triagem no dia **dentro do ClickUp** + a varredura final às 19h; o app só mostra "staging: N".)*
3. *(TRAVADO 5ª rodada — A2.3: são **dois ritos** — 19h fecha o trabalho, ~21h fecha o dia pessoal/reflexão.)*

---

### A3 · Fechamento noturno
**Objetivo:** fechar o loop do dia — diário cru → estruturado pela IA → **Leo aprova** — mais um destaque ressurgido e o scorecard de rotinas, em 10-15 min.

**Gatilho:** evento ("quando termino o jantar / vou deitar") com âncora ~21h; jamais um alarme punitivo.

**Sub-fluxo:**
1. Leo despeja o dia por voz/texto (1 campo, sem estrutura). — superfície: **app** / **Telegram**.
2. Hermes (profile capturas) estrutura no formato `diario` e **mostra a versão** para aprovação. A IA NUNCA grava sem o OK (lei nº3). Origem: fala crua → **raw imutável** em `1- Inbox/Raw/` → nota estruturada `Daily/YYYY-MM-DD.md`. Superfície: **Obsidian** (via GitHub MCP), gravação **só após aprovar**.
3. **1 destaque ressurgido + 1 frase de aplicação** (dose diária estilo Readwise): o sistema reapresenta 1 citação/insight de leitura antiga e pede 1 frase de como aplicar. Origem: **vault** (Leituras/Knowledge) → reapresentação → append no diário.
4. **Scorecard de rotinas do dia** (binário: fez/não fez skincare, treino, leitura...). Check visível = dopamina. Dia quebrado → **replanejar, não envergonhar** ("never miss twice", meta 20/30, não 30/30). Rotina/exercício furado alimenta o **motor de cobranças unificado** (C10): a régua de escalada cobra o *padrão* de furos, nunca o furo isolado.
5. Compara intenção (estado/prioridades do A1) × realizado — insumo do dashboard semanal (W12).

**Notificações:** empurrão seco à noite. Se rotinas furarem 3x seguidas, o Mentor (C11) entra com voz — mas o fechamento em si nunca cobra por humor.

**Hoje vs falta:**
- **Hoje:** o modo `diario` existe no contrato de captura do vault (raw→estruturado→aprova) e roda via Hermes.
- **Falta:** o rito empacotado (destaque ressurgido + scorecard) no app; o resurfacing diário; o scorecard binário persistido para o dashboard.

**Decisões abertas:**
1. *(TRAVADO 6ª rodada — A3.1: dado cru do check em **sqlite local** (só a máquina lê) + **visão** no app/dashboard C12. "Sem SQL em nuvem".)*
2. **Resurfacing: Anki real ou dose leve própria?** → Recomendo **dose leve no rito** (estilo Readwise) para insight/citação, e **Anki só para memorização dura** (W8/W13). Pesquisa confirma a separação.
3. *(TRAVADO 6ª rodada — A3.3: punição = **PONTOS sobre as Conquistas N1-4** — fazer ganha, furar **desconta pouco**; o scorecard <85% + o Mentor são a dor principal. **Linguagem jamais envergonha** (lei nº4). **Stakes reais/anti-charity FORA do v1** — só se o kaizen C24 provar necessidade.)*

---

### A4 · Review semanal
**Objetivo:** o rito de 20 min que impede o cemitério — a IA fecha a semana por ele (resumo, padrões, foco), ele aprova; e a quarentena de ideias (W17) é esvaziada.

**Gatilho:** **domingo 20h** (travado na 3ª rodada). Empurrão + o review **já vem pré-gerado** (não começa em branco). No **1º domingo do mês**, funde com o review mensal (A5) numa sessão estendida — um rito só.

**Sub-fluxo:**
1. Hermes lê os arquivos novos da semana (`Raw/`, `Daily/`, `Reflexoes/`, `Knowledge/`, `Empresa/Inbox/`) e **gera** `Fechamentos/Weekly/YYYY-WW.md`: resumo (3 frases), padrões recorrentes, conquistas, o que travou, ideias a graduar, foco da próxima semana. Origem: **vault** → síntese IA → **vault** (após aprovar). Superfície: **Obsidian**/app.
2. Leo revisa e aprova/corrige (lei nº3). — superfície: **app**.
3. **Scorecard semanal %** estilo 12WY (meta ≥85%): rotinas feitas ÷ planejadas, tarefas fechadas, cobranças resolvidas. Número frio, não humor (lei nº6). Origem: **ClickUp** + scorecard de rotinas → cálculo → **dashboard** (W12).
4. **Esvaziar o inbox de ideias** (W17): cada `#idea/graduating` vira projeto, knowledge, fica, ou morre. Sem review vivo, a quarentena vira lixão.
5. **Rerise:** decide qual **1 nova rotina** entra na próxima semana (onboarding progressivo, 1/semana).
6. **Temas da semana (NOVO 5ª rodada):** eventos/compromissos com **dia + hora** (ex.: "médico dia 14 às 15h") entram no plano da semana **E** viram lembrete no **próprio dia/hora** (mesmo scheduler de hora marcada do D18). Origem: captura + **calendários** (Outlook read-only + GCal) → plano semanal + scheduler → **app** (superfície de Calendário, F); um evento criado por captura pode ser **inserido no GCal** com aprovação (lei nº3). Aparecem no resumo de agenda do A1b.

**Notificações:** empurrão de domingo. Se o Leo pular o review 2 semanas seguidas, o Mentor (C11) intervém — é o rito que segura o sistema inteiro.

**Hoje vs falta:**
- **Hoje:** o `review semanal` existe como comando no vault (`CLAUDE.md`, hoje marcado dom **22h** — corrigir para 20h) e o review W27 **já foi auto-gerado** — mas com ZERO dado de execução (o loop nunca engatou).
- **Falta:** puxar dados de execução reais (ClickUp + scorecard em **sqlite local**); o esvaziamento de ideias no app; o Rerise; o scorecard %; a fusão com o mensal no 1º domingo.

**Decisões abertas:**
1. *(Resolvido 3ª rodada: **domingo 20h**, travado; corrigir o comando do vault de 22h→20h. No 1º domingo o mensal funde neste rito.)*
2. *(TRAVADO 6ª rodada — A4.2: Rerise **gated pelo scorecard** — só sobe 1 rotina nova quando as vigentes estão **≥85%**.)*
3. *(TRAVADO 6ª rodada — A4.3: graduação de ideias **no app** — 1 toque por ideia; a IA escreve no **vault** via Hermes.)*

---

### A5 · Reviews maiores (mensal / trimestral / anual / 10 anos)
**Objetivo:** subir a régua da reflexão — sintetizar semanas em mês, meses em trimestre, até o plano de 10 anos, sem reconstruir estrutura.

**Gatilho:** mensal = **1º domingo do mês, 20h — FUNDIDO ao review semanal** daquele domingo (sessão estendida, um rito só, 3ª rodada); trimestral/anual = âncoras de calendário.

**Sub-fluxo:**
1. Mensal (no 1º domingo, logo após o semanal A4, na mesma sessão): Hermes lê os 4-5 weeklies do mês → gera `Fechamentos/Monthly/YYYY-MM.md` (síntese expandida + objetivos mensuráveis). Origem: **vault** → síntese → **vault** (aprova). Superfície: **Obsidian**/app. Não é um rito separado — é o semanal estendido.
2. **Balanço patrimonial = MENSAL (travado 5ª rodada):** entra no review do 1º domingo (ativos/passivos/PL, base Anual.xlsx) — não mais só trimestral. Trimestral/Anual revisam o plano macro. Origem: dados financeiros → revisão → **vault** (W19).
3. Cada nível revisa e ajusta o nível acima (semana→mês→trim→ano→10a) — cadência desejada explícita do Leo.

**Notificações:** empurrão no início do mês; o Mentor entra quando há **desvio do plano macro** (não só atraso pontual).

**Hoje vs falta:**
- **Hoje:** `review mensal` existe como comando no vault (hoje "último domingo 14h" — mudar para **1º domingo, fundido ao semanal**).
- **Falta:** a fusão mensal+semanal; trimestral/anual/10a; a costura com a hierarquia de planos (W19) e o balanço patrimonial.

**Decisões abertas:**
1. *(Resolvido 3ª rodada: mensal = **1º domingo, fundido ao semanal**; o balanço patrimonial entra nele — travado 5ª rodada.)*
2. *(TRAVADO 6ª rodada — A5.2: **ciclo de 12 semanas (12WY)** no lugar de trimestre-calendário — já é a linguagem do scorecard. Ver W19.)*

---

## B — Entradas (como o mundo entra no sistema)

### B6 · Captura universal
**Objetivo:** um só canal onde qualquer coisa entra sem exigir decisão — a inteligência mora na triagem, não na captura (lei nº2).

**Gatilho:** o Leo tem algo na cabeça — a qualquer hora, qualquer lugar.

**Sub-fluxo:**
1. **Um campo** (voz Wispr ou texto) — **captura pelo APP é primária (travado 5ª rodada)**, não só Telegram. Zero escolha de categoria na hora. — superfície: **app** (Telegram = secundário/rua).
2. Texto → `POST /capture` (canal único) → Hermes (profile capturas) **detecta o modo** por palavra-chave; sem palavra = `captura` default → vai pro **Raw** imutável e é triado depois. Origem: fala → BFF → Hermes → **vault** `1- Inbox/Raw/`.
3. Se for tarefa **pessoal**: Hermes propõe destino (área/ClickUp), Leo confirma. To-dos NUNCA moram no vault — vão pro **ClickUp**.
4. Se for tarefa de **trabalho** capturada no correr do dia: cai na **lista intermediária (staging)** do ClickUp sem exigir triagem na hora (lei nº2); migra pras listas finais nas janelas de triagem (W2/W14). **Exceção — prazo curto:** "cobrar o Fulano da entrega às 14h" fica VIVO no staging e o Aeternum lembra **na hora** (W18), sem esperar a triagem.
5. Dois tipos de lembrete distinguidos na captura: **"eu preciso fazer X"** (minha tarefa) ≠ **"cobrar Fulano de Y às 14h"** (follow-up de terceiro). **NOVO (5ª rodada):** captura com **hora própria** ("entregar o relatório às 15h") usa o **mesmo scheduler de hora marcada do D18** — vale para **tarefa própria**, não só follow-up de terceiro.
6. Resposta seca ao Leo: "✅ anotado" (check visível = dopamina). A estruturação real acontece na triagem ou na hora se for óbvio.
7. Os 10 modos do contrato de captura (`captura`, `diario`, `livro:`, `conhecimento`, `reflexao`, `identidade`, `ideia`, `relacao`, `coach`, `empresa`) são reconhecidos por **palavra-chave falada**, não por menu.

**Notificações:** nenhuma na captura (é entrada, não cobrança). O que reaparece é responsabilidade da triagem/digest.

**Hoje vs falta:**
- **Hoje:** `/capture` funciona (canal único → Hermes); o contrato de 10 modos existe no vault; Telegram gateway funciona (@Suwkz_bot, só Leo).
- **Falta:** o app expor os modos sem virar menu; o profile default está **descasado** ("Leitura" em vez de captura); o round-trip tarefa→ClickUp; a **lista de staging** e a distinção dos dois tipos de lembrete (minha-tarefa vs cobrar-terceiro).

**Decisões abertas:**
1. *(TRAVADO 5ª rodada — B6.1: captura cega por padrão (Hermes detecta a palavra-chave) + "dial" opcional de modo. **NOVO:** um **tooltip/cheatsheet** no app com as palavras-chave e os modos, pra ele não precisar decorar — liga com o Manual/SOP, ver F.)*
2. **Corrigir o profile default** de "Leitura" para o de captura. → **corrigir já** — é bug, não decisão. Lei: captura simples.
3. *(TRAVADO 5ª rodada — B6.3: keywords **"cobrar"/"funcionário"** (+ nome/hora) marcam follow-up de terceiro; **na dúvida, a IA decide** e o Leo corrige. `citação` verbatim segue como risco a testar no Wispr.)*

---

### B7 · Sessão de leitura (áudio contínuo)
**Objetivo:** transformar leitura falada em nota estruturada no vault, sem quebrar o fluxo de ler — a lane #1 (D-11). **Redesenhada (5ª rodada): áudio contínuo no app, não ditados curtos.**

**Gatilho:** abrir a sessão (`livro: [título], página X`); a partir daí é **gravação de áudio contínua** no app.

**Sub-fluxo:**
1. O app **grava áudio contínuo** e transcreve **nativamente** — **não Wispr** (que limita ~5min; leitura é longa). — superfície: **app** (gravação nativa + transcrição).
2. **Hooks falados** dentro do áudio: **"quote"** → citação **verbatim**; **"comentário"/"comentários Leo"** → teoria/entendimento dele; demais modos (`ideia`, `coach`, `lista`) por palavra-chave. Origem: áudio → transcrição → parse por hook.
3. **Sessão cronometrada:** ao fechar, gera log **{livro, duração, páginas lidas, notas}** → **lista de sessões por livro** (integra com D23 e C12: **sessão = duração**).
4. **`compilar`** finaliza: **uma** chamada Hermes transforma o buffer da sessão em **nota estruturada no vault**; `lista` sai pro destino de compras; a IA sugere candidatos a Anki (W13, ficção não gera card). O vault recebe **só na compilação**.

**Notificações:** lembrete de revisão de leitura = resurfacing no A3 (não cobrança).

**Hoje vs falta:**
- **Hoje:** a gramática de modos existe (CAPTURE-GRAMMAR-SPEC); Hermes profile Leitura.
- **Falta:** **gravação de áudio nativa + transcrição no app**; os hooks falados; o cronômetro + log de sessão por livro; o buffer persistente + compilação única (ver B7.1).

**Decisões abertas:**
1. **B7.1 — persistência durante a sessão (recomendação REVISADA 5ª rodada):** a anterior (1 commit no vault por fala, ~10s cada) era **inviável**. → **Buffer LOCAL PERSISTENTE no app** durante a sessão (sobrevive fechar o app) + **autosave periódico no BFF** (sqlite, scaffolding) + **"compilar" → 1 chamada Hermes → nota no vault**. O vault recebe só na compilação.
2. **`lista` vai pra onde?** → **ClickUp (lista Pessoal, tag compras)** — mantém "uma home por coisa" (compras = tarefa, não conhecimento).
3. **Transcrição nativa: qual engine?** → a decidir (STT do device / lib on-device / serviço); requisito: aguentar sessão longa e **preservar `quote` verbatim** (o risco que o Wispr tinha).

---

### B8 · Aprendizado / estudo → Anki
**Objetivo:** capturar o que o Leo aprende de forma que **volte** para memorização dura (ele usa Anki de verdade).

**Gatilho:** `conhecimento` (palavra-chave) ou marcar `★` numa sessão de leitura.

**Sub-fluxo:**
1. Captura de conceito → **Raw** imutável; Hermes propõe estrutura no modo `conhecimento`. Origem: fala → **vault** `1- Inbox/Raw/`.
2. **Leo revê/estuda** o material e aprova a nota estruturada (a IA não decide o que ele aprendeu). Destino: **vault** `04 - Main Notes/Knowledge/` com **seção `## Anki Cards`** no **template real do Leo — Frente / Meaning / Example / Hook** (a IA preenche os 4, Leo aprova). Superfície: **Obsidian**. Ordem refinada: captura → Leo estuda → Obsidian → só então card.
3. Só então os cards entram na fila `#anki/pending`; sincronizam com o Anki via W13 (com gate de aprovação). A nota-fonte fica no vault, o card no Anki (glass-not-store).

**Notificações:** o lembrete "revisa X cards" é o cron do Hermes (motor de nudge), não uma cobrança dura.

**Hoje vs falta:**
- **Hoje:** modo `conhecimento` + seção Anki + tag `anki/pending` existem no contrato.
- **Falta:** o gate "Leo estuda antes de virar card"; a fila real `#anki/pending` → Anki (ver W13).

**Decisões abertas:**
1. **Mesmo mecanismo do W13** (AnkiConnect + fila `#anki/pending`) — decidir uma vez. Recomendação lá.
2. *(TRAVADO 5ª rodada — B8.2: template de card = **Frente / Meaning / Example / Hook**; a IA preenche, Leo aprova.)*
3. *(TRAVADO 6ª rodada — decks Anki por DOMÍNIO: Finanças & Investimentos · Direito · Tecnologia & IA · Pessoas & Comunicação · Mundo & Notícias · Vida & Mente. A **IA sugere o deck** por card; Leo confirma.)*

---

### B9 · Terapia
**Objetivo:** dar um lugar seguro e privado para material de terapia/saúde mental, com privacidade máxima em notificação.

**Gatilho:** `terapia` (palavra-chave) — tipicamente após sessão semanal com o psicólogo.

**Sub-fluxo:**
1. Captura → Hermes estrutura como reflexão sensível. Origem: fala → **raw** → nota em `02 - Personal/` (Reflexões/Identidade). Superfície: **Obsidian**.
2. Conteúdo marcado como sensível: NUNCA aparece em lockscreen/preview (lei nº7) — só chamadas neutras.
3. Pode gerar ação (não diagnóstico): ex.: "marcar psiquiatra" → tarefa em **ClickUp/Saúde** (W15). O compromisso "psiquiatra em 30 dias" está **vencido há 22 dias** — caso de teste da escalada (C11).

**Notificações:** só neutras ("você tem 1 pendência de saúde"), jamais conteúdo. O Mentor pode cobrar o compromisso vencido — com cuidado, número frio, sem expor o tema.

**Hoje vs falta:**
- **Hoje:** modo existe no contrato (mapeado a reflexão/identidade); privacidade é lei declarada.
- **Falta:** a garantia técnica de que notificação nunca vaza conteúdo; a ponte sintoma/compromisso → tarefa de saúde.

**Decisões abertas:**
1. *(TRAVADO 5ª rodada — B9.1: terapia = **flag de sensibilidade** sobre reflexão, não um silo novo.)*
2. *(TRAVADO 5ª rodada — B9.2: Decision Journal **sem terapia** — só decisões pessoais.)*

#### Sub-workflow "Edificação" (NOVO 5ª rodada — atravessa B9 / A4 / E20)
**Objetivo (palavras do Leo):** "aprendo hacks mas esqueço de aplicar; preciso me edificar e construir." Fechar o loop entre aprender sobre si e **aplicar**.
1. **Registro contínuo** de aprendizados sobre si (na terapia **e** no dia a dia): defeitos, hacks de procrastinação, insights → captura com **tag própria** (`field/edificacao` ou similar). Origem: captura → **vault** (reflexão sensível quando for terapia).
2. **Vazão semanal/mensal:** no review (A4/A5) a IA **agrega "o que você aprendeu sobre si"** e **propõe um plano de ação/prática**. Leo aprova.
3. **Acompanhamento pelo Mentor (E20):** um hack aprovado vira **lembrete contextual/rotina**; a **aderência entra no scorecard** (C12) e na régua do Mentor (C11) — sem vergonha.

---

## C — Motores (o que roda por baixo, sem o Leo pedir)

### C10 · Motor de cobranças (unificado)
**Objetivo:** o coração da disciplina — um só motor reapresenta todo dia TUDO que precisa de ação (tarefas + obrigações financeiras + saúde + **rotinas/exercícios furados**), persistente mas **sem spam**, até morrer (resolvido) ou ser replanejado.

**Gatilho:** cron diário (manhã), no slot "organizar cobranças do dia" (~9h, antes do daily).

**Sub-fluxo:**
1. Cron lê as fontes abertas: tarefas (**ClickUp**, todas as listas — inclui financeiro e saúde) + **rotinas furadas** do scorecard (W3/W12). Origem → regras de cadência (`cadence.py`, portadas do cutuca, 50 testes) → seleção.
2. **Regras determinísticas** (`needs_nudge`): cobra se **atrasada** (qualquer), **vence em breve** (hoje..+N) ou **parada há ≥N dias** (staleness). Nunca cobra item fechado. **Rotina furada entra pelo padrão, não pelo furo isolado** (lei nº4: replanejar, não envergonhar) — 1 furo não cobra; padrão (ex.: 3 furos) cobra.
3. Monta o digest único ordenado por urgência e entrega **no app** (tela Revisão + notificação in-app, app-first). Origem: seleção → `format_digest` → **app**; **Telegram** cobre a transição enquanto o push in-app não existe.
4. Cada item some quando resolvido; reaparece amanhã se não. "Reappears daily until killed, firmer as it ages" (D-7). Financeiro/saúde entram determinísticos (vencimento); rotina entra por padrão de furo.

**Notificações:** empurrão diário seco, 1 digest de **fonte única** (o cron calcula uma vez; entrega in-app + Telegram na transição, sem duplicar cadência — D-14). Preview neutro (lei nº7): saúde/terapia nunca aparecem com conteúdo.

**Hoje vs falta:**
- **Hoje:** `cadence.py` roda; `/digest` (app) e `/internal/run-digest` (push) existem; caminho ClickUp real validado 2026-07-05.
- **Falta:** **não há cron** — nada chama `/internal/run-digest`; **push in-app morto** no Expo Go (token null) — app-first exige dev build + VPS; **staleness desligado** na fonte ClickUp (`update_offset=None`) → hoje só cobra por vencimento; **rotinas furadas ainda não entram** (o scorecard não persiste). VPS pausado (o digest de manhã exige always-on).

**Decisões abertas:**
1. **App-first: o que roda no Telegram na transição, e quando cortá-lo?** → Recomendo **manter o Telegram como espelho do digest até o dev build + VPS estarem de pé**; depois vira opcional (rua/fallback), nunca obrigatório. A direção (tudo pelo app) está decidida; isto é sequenciamento. (Decisão nº3.)
2. **Ligar staleness na fonte ClickUp?** → Recomendo **ligar depois de ver os dados reais** (como o código já comenta) — senão inunda a Revisão com tudo não-tocado em 3 dias. Começar só por vencimento.
3. **Rotina furada: qual o limiar de "padrão" que cobra?** → Recomendo **≥3 furos na mesma rotina** (ou o gatilho do Mentor, C11), nunca o furo isolado — config, não hardcode. Lei nº4 (anti-vergonha).

---

### C11 · Escalada de tom + Mentor-quando-vira-padrão
**Objetivo:** cobrar mais firme conforme o desvio cresce — mas regulado por **número frio**, não por humor; e chamar o Mentor com voz só quando vira **padrão**.

**Gatilho:** automático, embutido no digest (C10) e nos ritos.

**Sub-fluxo:**
1. Cada item ganha um tom pela idade do atraso (`cadence.tone`): **🟡 no prazo · 🟠 leve (1-2d) · 🔴 firme (3-6d) · 🚨 urgente (7+d)**. Origem: `days_overdue` → marcador → linha do digest.
2. Nudge do dia a dia = **seco** (só o marcador). Sem interval-spam (D-7).
3. **Mentor entra com voz quando vira padrão:** 3+ furos na mesma rotina, pendência > X dias, ou **desvio do plano macro** (≥85% não batido). Vale para qualquer tipo do motor unificado (tarefa/financeiro/saúde/rotina). Origem: scorecard (W12) + histórico → gatilho → mensagem do Mentor (W20). Superfície: **app** (Telegram só na transição).
4. Escalada suave→dura regulada pelo desvio mensurável (scorecard 12WY), não pelo humor do dia (lei nº6). Dia quebrado = replanejar, nunca envergonhar.

**Notificações:** o marcador de tom viaja no digest; a fala do Mentor é um evento raro e deliberado, com privacidade (nunca expõe o tema sensível).

**Hoje vs falta:**
- **Hoje:** a escala de tom (`tone`, 4 níveis) existe e roda.
- **Falta:** o gatilho "vira padrão → Mentor" (precisa do scorecard/histórico, que ainda não persiste); e há **DUAS escalas de severidade divergentes** (cadence markers no back vs re-parse no front) — precisam convergir para uma fonte.

**Decisões abertas:**
1. **Uma escala de severidade, não duas.** → Recomendo **o back (`cadence.py`) é a fonte; o front só exibe** — nunca re-derivar no front. É bug de arquitetura, não preferência.
2. **Limiares do "vira padrão"** (quantos furos, quantos dias)? → Recomendo **config, não hardcode** (D-7): 3 furos / pendência > 7d / scorecard < 85% como default, ajustável.
3. **Mentor cobra compromissos vencidos sensíveis (ex.: psiquiatra 22d)?** → Recomendo **sim, mas neutro e privado**: cobra a ação ("marcar consulta"), nunca expõe o tema. É o caso de teste declarado.

---

### C12 · Dashboard semanal (IA)
**Objetivo:** transformar a semana em números que o Leo entende de relance (visual, KPIs > canvas), fechando o loop de reflexão **por ele**.

**Gatilho:** gerado no review semanal (A4) e consultável a qualquer hora.

**Sub-fluxo:**
1. Agrega a tríade de medição: **rotina = binária** (fez/não), **sessão = duração** (W23), **tarefa = entrega** (ClickUp). Origem: **ClickUp** + scorecard de rotinas (**sqlite local**) + logs de sessão → cálculo → **dashboard**. A geração pesada (síntese, gráficos) roda na **lane batch** (`claude`/`codex` CLI no PC), não no Hermes interativo.
2. Quantified-self do Drive: peso, sono, passos, exercício, álcool, livros/páginas, journal-feito → métricas do dashboard. Origem: entradas manuais/Garmin → agregação.
3. **Scorecard %** (12WY, meta ≥85%) + **"Self Honesty"** (nota subjetiva por área) + **aderência a objetivos acumulativos** (D19, ex.: "academia este ano"). Superfície: **app** (Home/Radar) / **Obsidian** (dashboard dataview). O dashboard é **publicável no GitHub** (markdown/dataview gerado na **lane batch**).
4. Alimenta o gatilho do Mentor (C11): desvio mensurável → escalada.

**Notificações:** nenhuma direta — o dashboard é consulta; quem cobra é o C11 a partir dos números.

**Hoje vs falta:**
- **Hoje:** a Home v2 tem o formato (Radar, KPIs mono), mas os números são **hardcoded**; o vault tem plugin dataview.
- **Falta:** a agregação real da tríade; persistir rotina binária e sessões em **sqlite local** (só a máquina lê); a geração pela **lane batch**; o "Self Honesty"; ligar ao Mentor.

**Decisões abertas:**
1. **Recompensa/Punição ou só Conquistas N1-4?** → Recomendo **Conquistas N1-4 + Self Honesty**, sem punição (lei: jamais punitivo). (Decisão nº7.)
2. **Dashboard mora no app, no vault, ou ambos?** → Recomendo **app = a vidraça de consulta** (KPIs de relance), **vault = o registro dataview**. **Cálculo pesado na lane batch** (PC), estado em sqlite local, exibição no app. Glass-not-store.
3. **Métricas manuais (peso/álcool) — onde entram?** → Recomendo **campos no fechamento noturno** (A3), não uma planilha à parte (cemitério).

---

### C13 · Sincronização Anki (AnkiConnect)
**Objetivo:** levar os cards aprovados do vault para o Anki de verdade, para a repetição espaçada acontecer — via API local, não mais um "export" manual.

**Gatilho:** fila no vault (`#anki/pending`) alimentada pela sugestão de candidatos da IA (fim de sessão / review); sincroniza quando o Anki desktop está aberto (âncora ~domingo 20h30, mas oportunístico).

**Sub-fluxo:**
1. Cards aprovados (de `conhecimento` W8 + itens `★` de leitura W7) entram na fila `#anki/pending` no vault. Origem: **vault** `04 - Main Notes/Knowledge/` + Leituras.
2. Quando o Anki desktop está aberto, o sistema empurra os cards via **AnkiConnect** (API HTTP local). Leo aprova o lote (lei nº3: IA sugere, Leo aprova). Destino: **Anki**; a nota-fonte fica no vault.
3. Atualiza a tag `pending` no vault após sincronizar. `.apkg`/TSV fica como **fallback** se o AnkiConnect não estiver disponível.

**Notificações:** lembrete leve in-app ("N cards esperando sincronizar") quando a fila cresce; sem cobrança dura (retenção não é dívida).

**Hoje vs falta:**
- **Hoje:** as notas ganham `anki/pending`; o rito de domingo está no plano.
- **Falta:** **a integração AnkiConnect não existe**; a fila real; a sugestão de candidatos pela IA.

**Decisões abertas:**
1. **Mecanismo: AnkiConnect vs TSV manual? (aberto pro Leo, decisão nº2)** Duas opções honestas:
   - **AnkiConnect** (API HTTP local) — **sem passo manual**, sincroniza sozinho quando o Anki abre; custo: exige o **Anki desktop aberto + plugin** instalado no PC.
   - **TSV/CSV manual** — **zero dependência** (funciona em qualquer máquina), mas o **import é um passo manual** = fricção, e fricção mata hábito (lei nº1: vazão).
   → **Recomendo AnkiConnect como alvo** (elimina a fricção que já matou hábitos do Leo); **TSV aceitável como degrau** enquanto a integração não existe. **Revisitar quando houver VPS** (o Anki desktop mora no PC, não no VPS).
2. **Sincronizar contínuo ou em lote no domingo?** → Recomendo **oportunístico** (quando o Anki abre) + varredura no review (A4). Contínuo exige o Anki sempre aberto.

---

### C24 · Agente de melhoria (kaizen)
**Objetivo:** o sistema melhora a si mesmo — observa como o Leo usa o Aeternum (o que trava, o que é ignorado) e **PROPÕE** ajustes, sem nunca aplicar sozinho.

**Gatilho:** sinais micro colhidos no review semanal (A4) + uma **proposta consolidada 1x/mês** (semanal viraria ruído).

**Sub-fluxo:**
1. Coleta de sinais: o que foi capturado e nunca triado, nudges ignorados, ritos pulados, atritos de fluxo. Origem: **telemetria** (a mesma do dashboard, em **sqlite local** — só a máquina lê) → agregação.
2. Análise na **lane batch** (`claude`/`codex` CLI no PC, FDS/madrugada): cruza os sinais e formula hipóteses de melhoria (ex.: "o rito das 19h é pulado toda 6ª → encurtar ou mover?").
3. **Proposta mensal** apresentada ao Leo no review estendido do 1º domingo (A5): lista de ajustes com o porquê. Leo aprova/recusa cada um. Destino: mudanças de config/cadência **só após aprovação** (lei nº3 estendida ao próprio sistema).

**Notificações:** nenhuma diária; a proposta chega no rito mensal. Nunca cobra — só sugere.

**Hoje vs falta:**
- **Hoje:** nada — não existe telemetria nem agente de melhoria no as-built.
- **Falta:** a telemetria persistida (**sqlite local**); a lane batch; o formato da proposta mensal; o loop de aprovação.

**Decisões abertas:**
1. **Cadência: micro-semanal + consolidado mensal, ou só mensal?** → Recomendo **micro no semanal (só registra sinais) + proposta 1x/mês** (a 4ª rodada já indica): semanal viraria ruído e o Leo pediria pra desligar.
2. **O kaizen pode mexer em config sozinho se for trivial?** → Recomendo **não**: SEMPRE propõe, nunca aplica — é o próprio sistema respeitando "a IA não grava sem aprovar". Um agente que se auto-modifica sem gate não vale a economia de 1 toque.
3. **Telemetria: o que é ético registrar?** → Recomendo **só metadados de uso** (contagens, timestamps, flags), **nunca o conteúdo** das capturas sensíveis (lei nº7). O kaizen olha padrões de comportamento, não o que o Leo escreveu na terapia.

---

## D — Gestão (as coleções que o sistema mantém)

### D14 · Tarefas por área
**Objetivo:** ver e mexer em todas as tarefas por área de vida, de uma home só, com recência ("quando foi a última vez").

**Gatilho:** o Leo abre a tela Tarefas, ou uma captura vira tarefa.

**Sub-fluxo:**
1. App lista tarefas agrupadas pelas listas do ClickUp. Hoje 4 (Trabalho/Finanças/Saúde/Pessoal); **estrutura final (spec §8): 10 listas = Staging + Trabalho (ITER) + as 8 áreas de vida** (Corpo, Saúde Mental, Responsabilidade, Finance, Carreira, Estudo, Relacionamentos, Lazer). Origem: **ClickUp** (`GET /tasks`, o BFF mapeia área→list_id) → agrupamento → **app**.
2. Criar/concluir/editar + filtro por área + recência ("última vez há X"). Round-trip pro ClickUp em cada ação.
3. A **lista staging** de trabalho e **Aguardando** (W18) convivem com as áreas. **Triagem do staging = dentro do ClickUp** (a IA salva lá; Leo promove quando quiser; agente IA ajuda em lote). O app não constrói UI de triagem (só o Shutdown mostra "staging: N").

**Notificações:** nenhuma direta (a cobrança é o C10). A tela é o "onde eu mexo".

**Hoje vs falta:**
- **Hoje:** CRUD + complete + detail existem (`/tasks`); agrupamento por 4 áreas; caminho ClickUp validado.
- **Falta:** recência real (staleness desligado); editar no app; a **reestruturação para as 10 listas** (8 áreas + Trabalho + Staging); o Aguardando como tag transversal.

**Decisões abertas:**
1. **Mapeamento ClickUp — RESOLVIDO na spec (§8): 10 listas.** A separação "mapa-de-vida × listas operacionais" que ficara em aberto na 5ª rodada foi decidida: **Staging + Trabalho (ITER operacional, lista própria) + as 8 áreas de vida** (Corpo · Saúde Mental · Responsabilidade · Finance · Carreira · Estudo · Relacionamentos · Lazer); **Aguardando = tag/status transversal**. Princípio: *"Carreira = pra onde vou; Trabalho = o que devo HOJE"* — o volume diário do ITER não polui a visão de carreira. **Evolução:** 5ª rodada recomendava 8 listas com a separação em aberto → 6ª rodada/spec crava **10 listas**.
2. **Staging e Aguardando (travado 5ª rodada):** **staging = 1 lista dedicada**, com a **triagem NO ClickUp** (sem UI de triagem no app; o Shutdown só mostra "staging: N"). **Aguardando = status/tag** dentro das áreas.
3. *(Aceito 5ª rodada — recência: ligar staleness depois de ver dados reais.)*

---

### D15 · Saúde
**Objetivo:** tratar saúde como workflow — médicos recorrentes, exames, sintomas/dores — gerando **ação** (marcar/comprar), não diagnóstico.

**Gatilho:** captura de sintoma/lembrete de saúde, ou recorrência vencendo (ex.: dentista 6/6m).

**Sub-fluxo:**
1. Captura ("dor no joelho", "dentista atrasado") → Hermes → tarefa em **ClickUp/Saúde**. Origem: fala → tarefa acionável.
2. Médicos com frequência (dentista 6/6m etc.) = tarefas **recorrentes** que o digest (C10) cobra quando vencem.
3. Sintomas/esquecimentos registrados geram ação (marcar médico, comprar remédio), não análise clínica.

**Notificações:** via digest (C10), sempre neutras no preview (lei nº7 — saúde é sensível).

**Hoje vs falta:**
- **Hoje:** lista Saúde existe no ClickUp; o mock tem "Dentista — há 7 meses".
- **Falta:** recorrências configuradas; a ponte sintoma→ação; carga real dos médicos/exames.

**Decisões abertas:**
1. **Recorrência médica: nativa do ClickUp ou regra própria?** → Recomendo **recorrência nativa do ClickUp** quando der; senão o motor de cadência trata como "vence a cada N dias".
2. **Sintomas viram nota (vault) ou só tarefa (ClickUp)?** → Recomendo **tarefa** (o objetivo é ação); nota só se virar padrão a discutir na terapia (B9).

---

### D16 · Obrigações financeiras recorrentes
**Objetivo:** nunca mais esquecer boleto/NF/IR — motor determinístico de cobrança financeira; a primeira carga real das listas.

**Gatilho:** cron (vencimentos mensais) + season anual (IR).

**Sub-fluxo:**
1. Carga inicial: **recriar à mão** as recorrentes (8 cartões + Unimed + condomínio) em **ClickUp/Finanças**; a **Pagamento Mensal.xlsx** vira **referência de conferência** (não fonte de import). Origem: planilha (referência) → tarefas recriadas.
2. ~10 boletos/mês + emitir NFs → tarefas com due date; o digest (C10) cobra.
3. IR anual = checklist de documentos com season. Origem: template anual → tarefas.

**Notificações:** via digest (C10). Financeiro é determinístico → cobrança limpa, sem drama.

**Hoje vs falta:**
- **Hoje:** lista Finanças existe; cadência cobra por vencimento.
- **Falta:** a carga da planilha; recorrências mensais; o checklist de IR; emitir-NF como tipo.

**Decisões abertas:**
1. *(TRAVADO 5ª rodada — D16.1: **RECRIAR as recorrências à mão** no ClickUp (não importar); a planilha vira **referência de conferência**.)*
2. *(Aceito 5ª rodada — D16.2: IR = **checklist no ClickUp** (execução) + SOP no vault (o "como").)*

---

### D17 · Quarentena de ideias (Someday/Maybe)
**Objetivo:** dar às ideias um lugar que não é lixão — capturadas leves, revisadas vivas, graduadas ou mortas com dignidade.

**Gatilho:** captura `ideia`; esvaziada no review semanal (A4).

**Sub-fluxo:**
1. `ideia` → nota em `1- Inbox/Ideias/` com tag `#idea/graduating` se promissora. Origem: fala → **vault**.
2. No review semanal (A4), cada ideia: vira **projeto**, vira **knowledge**, **fica**, ou **morre** (arquivo). Superfície: **app** (1 toque) → **vault** (Hermes aplica).
3. Sem review vivo, a quarentena vira lixão — por isso é acoplada ao A4 (lei: só funciona com review vivo).

**Notificações:** nenhuma direta; o A4 é o gatilho.

**Hoje vs falta:**
- **Hoje:** modo `ideia` + tag + comando `graduar` existem no vault.
- **Falta:** a graduação como fluxo de 1 toque no app.

**Decisões abertas:**
1. **Graduação no app ou só comando no vault?** → Recomendo **app** (baixa fricção) escrevendo no vault. (Mesma linha do A4.)

---

### D18 · Aguardando / delegações
**Objetivo:** rastrear o que o Leo delegou/está esperando de terceiros, para cobrar de volta na hora certa — inclusive follow-ups de **prazo curto** que não podem esperar a triagem.

**Gatilho:** captura de "cobrar Fulano de Y às 14h" (W6), no encerramento (A2), ou quando delega.

**Sub-fluxo:**
1. Follow-up marcado "aguardando [pessoa]" → tarefa/tag de espera no ClickUp. Origem: A2/captura → **ClickUp**.
2. **Dois relógios distintos:** (a) espera de fundo → o digest (C10) cobra quando passa do prazo ("parada há Xd"); (b) **prazo curto com hora dura** ("entrega às 14h") → fica VIVO no **staging** e o Aeternum lembra **na hora**, sem esperar a triagem (exceção da lei de triagem). Superfície: **app** (notificação in-app).
3. É a distinção "eu preciso fazer X" ≠ "cobrar Fulano de Y às 14h" (W6) rendendo dois comportamentos de lembrete.

**Notificações:** in-app (app-first). Prazo-curto = lembrete pontual na hora marcada; espera de fundo = via digest; o Mentor lembra se um follow-up crítico apodrece. Itens de hora marcada também aparecem na **superfície de Calendário** (F), junto de Outlook/GCal.

**Hoje vs falta:**
- **Hoje:** o campo assignee existe no shape de Task.
- **Falta:** o conceito "aguardando"; o lembrete de **hora marcada** (cobra na hora, não no digest); a cobrança por espera (depende do staleness, hoje desligado).

**Decisões abertas:**
1. **"Aguardando" é status, tag, ou lista?** → Recomendo **status/tag** dentro das áreas (não uma lista à parte) — mantém a home única. O prazo-curto vive no **staging** até resolver.
2. **Lembrete de hora marcada: quem dispara?** → Recomendo **cron/scheduler do sistema** (não só o digest matinal) — "às 14h" precisa de gatilho pontual, o que reforça a dependência de always-on (VPS).

---

### D19 · Hierarquia de planos (10a → ciclo → semana → dia)
**Objetivo:** um lugar só onde o plano de 10 anos desce até o dia, sem reconstruir estrutura — o antídoto ao cemitério de planilhas.

**Gatilho:** o Leo fará o **plano de 10 anos neste fim de semana** — a spec precisa definir onde mora e o formato para já nascer dentro do sistema.

**Sub-fluxo:**
1. Cadência: **diário → semanal → mensal → trimestral → anual → 10 anos**, cada nível linkando ao de cima. Origem/destino: **vault** (notas linkadas, dataview).
2. Insumo plurianual: 2026 empresa cash-flow, 2027 estudo, 2029 empresa estratégica → alimenta o plano de 10 anos.
3. Os reviews (A4/A5) revisam cada nível; o check-in/fechamento (A1/A3) executam o nível "dia".
4. **Objetivos acumulativos (NOVO 5ª rodada):** metas do tipo "rodar a rotina de academia este ano" — o **input diário acumula**; **todos os níveis de review** (sem/mensal/trim/anual) mostram um **dashboard de ADERÊNCIA** ao objetivo macro. Origem: check diário → acumulação (**sqlite local**) → dashboard (C12), **publicável no GitHub** (markdown/dataview gerado na **lane batch**).

**Notificações:** o Mentor cobra **desvio do plano macro** (C11), não o dia a dia.

**Hoje vs falta:**
- **Hoje:** o vault tem `05 Projetos` e templates; o plano de 30 dias existe como modelo (hora marcada + piso mínimo + cobrança).
- **Falta:** o formato/local canônico da hierarquia; a costura dos níveis; nascer antes do fim de semana.

**Decisões abertas:**
1. **Formato/local da hierarquia no vault?** → Recomendo **uma pasta de planos com nota por nível + links dataview** (10a↔ano↔trim↔mês↔semana↔dia); nada de nova planilha. **Urgente: o plano de 10 anos é este fim de semana.** (Decisão nº5.)
2. *(TRAVADO 6ª rodada — **12WY como o ciclo**, no lugar de trimestre-calendário. Liga ao A5.2.)*
3. **O plano de 30 dias (vence em 3 dias) vira o quê?** → Recomendo **o primeiro "ciclo" fechado** e insumo do review — não deixar morrer sem fechamento (never miss twice).

---

### D23 · Sessões de tempo focado
**Objetivo:** medir tempo de foco por projeto E por categoria de propósito (concentração/terapêutica), com metas de X horas/mês — a terceira perna da tríade (sessão = duração).

**Gatilho:** iniciar um bloco de foco (hobby/projeto, ex.: barquinho de madeira) via timer.

**Sub-fluxo:**
1. Timer ao vivo (app/Garmin) marca início/fim; OU log por voz a posteriori ("fiz 40min de barquinho"). Origem: timer/voz → sessão com {projeto, categoria, duração}.
2. Metas de X horas/mês por categoria; leitura conta por projeto E por categoria. Destino: agregação no dashboard (C12).
3. Carga inicial: migrar o Excel do barquinho.

**Notificações:** interstitial journaling nas transições de bloco = **opcional, só se disparado por timer** (não empurrar).

**Hoje vs falta:**
- **Hoje:** nada — sessões de foco não existem no as-built.
- **Falta:** o modelo de sessão (projeto+categoria+duração); timer; log por voz; integração Garmin; o cruzamento no dashboard.

**Decisões abertas:**
1. **Timer: app, Garmin, ou ambos?** → Recomendo **ambos, Garmin como satélite** (relógio é o que ele olha; app registra/agrega). O Garmin dispara/conta, o log final concilia no sistema. (Decisão nº6.)
2. **Sessão mora onde (persistência nova)?** → Recomendo **ClickUp com custom fields {categoria, duração}** OU time-tracking do ClickUp — evita DB novo (glass-not-store). A decidir contra a API real.
3. **Interstitial journaling: ligar por padrão?** → Recomendo **desligado por padrão, opt-in por timer** — senão vira fricção que mata o bloco.

---

## E — Conversa (a IA como interlocutor)

### E20 · Mentor
**Objetivo:** a voz de accountability que entra quando vira padrão — body double externo, anti-bajulação, ancorado nas notas do Leo.

**Gatilho:** disparado pelo C11 (padrão detectado) ou o Leo abre o modo Mentor no chat.

**Sub-fluxo:**
1. Modo Mentor (personality Hermes) puxa contexto: scorecard (C12), plano macro (W19), notas do vault. Origem: **Hermes memory** + **vault** + **ClickUp**.
2. Fala firme mas não humorada: cita as notas do Leo, aponta o desvio pelo número, **fecha com uma ação** (tarefa no ClickUp). Superfície: **app** (chat) / **Telegram**.
3. Respeita privacidade: cobra a ação sem expor o tema sensível.
4. **Acompanha a Edificação (5ª rodada):** hacks/aprendizados sobre si que o Leo aprovou (B9) viram lembretes contextuais/rotina; o Mentor cobra a **aplicação** e a aderência entra no scorecard (C12).

**Notificações:** o Mentor é o único que "fala com voz" — evento raro, deliberado (C11).

**Hoje vs falta:**
- **Hoje:** personality "mentor" existe no `config.yaml` do Hermes; o BFF só **prefixa um "chapéu" de modo** no prompt (não troca a personality real).
- **Falta:** trocar a personality real por modo; alimentar o Mentor com scorecard/histórico; o gatilho de padrão.

**Decisões abertas:**
1. **BFF troca personality real ou só prefixa chapéu?** → Recomendo **trocar a personality real** por modo — o "chapéu" é raso demais para o Mentor soar diferente do chat comum.
2. **Mentor proativo (empurra) ou só reativo (quando aberto)?** → Recomendo **os dois**: reativo sempre; proativo só quando C11 dispara (padrão), nunca spam.

---

### E21 · Conselho + Decision Journal
**Objetivo:** um "conselho" de perspectivas para decisões pessoais, com registro da decisão para revisar o acerto depois.

**Gatilho:** o Leo abre o modo Conselho para uma decisão pessoal.

**Sub-fluxo:**
1. Modo Conselho (personality "conselho") oferece múltiplas perspectivas; Leo decide. Superfície: **app** (chat).
2. A decisão + racional viram entrada de **Decision Journal** — **só decisões pessoais** (trabalho fora, por decisão do Leo). Destino: **vault** (após aprovar).
3. Revisão posterior (nos reviews A4/A5) confronta decisão × resultado.

**Notificações:** nenhuma; é sob demanda.

**Hoje vs falta:**
- **Hoje:** personality "conselho" existe no `config.yaml`.
- **Falta:** o Decision Journal como formato/local no vault; a revisão posterior.

**Decisões abertas:**
1. **Decision Journal mora onde?** → Recomendo **`02 - Personal/` (nota datada, append)**, revisada nos reviews. É reflexão, não tarefa.
2. **Trabalho realmente fora?** → Sim (decisão do Leo já registrada). Não reabrir.

---

### E22 · Chat persistente
**Objetivo:** um chat estilo Codex/Claude que **lembra** — hoje ele é decorativo; precisa persistir para virar o cockpit de conversa.

**Gatilho:** o Leo abre o Chat (qualquer modo: Capturas/Mentor/Conselho/Tarefas).

**Sub-fluxo:**
1. Tela larga = 2 colunas (histórico à esquerda agrupado Hoje/Ontem/Semana + conversa à direita); celular = histórico vira drawer. Seletor de modo (não abas). Superfície: **app**.
2. Cada mensagem persiste; "+ Nova" cria conversa real; busca no histórico.
3. **Chats por área (aprovado 3ª rodada):** a UI mostra **chats separados por área da vida** (treino, nutrição, relacionamento...), mas por baixo é **um agente só** (o Mentor) com o **contexto daquela área** carregado — não N personas. Uma área **gradua para persona própria** só se acumular material/uso real (o critério que evita o "persona zoo").

**Notificações:** nenhuma direta.

**Hoje vs falta:**
- **Hoje:** o design v2 do chat está aprovado; personalities existem no Hermes.
- **Falta:** **persistência** — hoje `CONVS` é hardcoded e "+Nova" é decorativo; o histórico não existe. Os **chats por área** (UI separada + um agente com contexto de área) e o critério de graduação.

**Decisões abertas:**
1. **Persistência onde: Hermes memory, BFF sqlite, ou vault?** → Recomendo **Hermes memory como dono da conversa** (é a memória do agente por design), com o BFF só refletindo sessão/ID. Não é conhecimento (vault) nem tarefa (ClickUp). (Decisão nº9.)
2. *(Resolvido 3ª rodada, decisão nº11: **chats separados por área na UI, um agente só por baixo**, com contexto de área; a área só vira persona própria se acumular material/uso. Resolve a tensão do "persona zoo" de 2026-07-04 sem multiplicar personas.)* Aberto só o **critério de graduação** — quanto uso/material promove uma área a persona.
3. **Histórico entre superfícies (app ↔ Telegram) é o mesmo?** → Recomendo **sim, um só fio** — o Hermes é o engine único; app-first, mas trocar superfície não deve bifurcar a conversa.

---

## F — Camada de superfícies (transversal, não é workflow)

Não é um workflow com sub-fluxo — é o mapa de **qual superfície faz o quê**, que atravessa todos os
24 acima. **Direção decidida (2ª/3ª rodada, reconfirmada): APP-FIRST** — o Leo quer fazer tudo pelo
app, inclusive receber notificação pelo app; Telegram deixa de ser obrigatório no fluxo.

- **App (Expo) = a superfície primária.** O Leo *abre, opera e é avisado* por aqui. Vidro sobre o Hermes, guarda nada canônico. Primeira coisa que ele olha de manhã: celular.
- **Telegram = secundário / ponte de transição.** Já funciona (@Suwkz_bot, só Leo, auto-start no boot) e **cobre a notificação enquanto o push in-app não existe**. Depois vira opcional (rua/fallback), nunca obrigatório.
- **Garmin = satélite.** Alarmes de rito + timers de bloco (W23). Não é app completo; conversa com o sistema via log/conciliação.
- **Obsidian (vault em GitHub) = home de conhecimento/reflexão.** Escrita via GitHub MCP, sempre após aprovação (lei nº3).
- **Manual/SOP no app (NOVO 5ª rodada) = tooltips + DIAGRAMAS dos fluxos.** O Leo é visual ("preciso de SOPs e diagramas"): uma seção de ajuda no app com o cheatsheet de captura (B6) e **diagramas** dos workflows, idealmente **renderizados a partir dos SOPs do vault** (gerados na lane batch).
- **Calendário no app (NOVO 6ª rodada) = agenda agregada.** Visão dia/semana juntando **Outlook** (profissional, **read-only best-effort com fallback** — o Graph API pode ser barrado pela TI/SSL corporativo; fallback = URL ICS publicada ou leitura best-effort), **Google Calendar** (pessoal, **IA lê e insere** via OAuth padrão, com aprovação — lei nº3), **itens de hora marcada** (D18/B6) e **ritos** (A1/A2/A3). Nada canônico no app.
- **Notificações = digest + escalada, privacidade sempre.** Fonte única (C10/C11); preview nunca carrega conteúdo sensível (lei nº7). **Custo honesto do app-first:** push in-app exige **dev build (não Expo Go) + backend always-on (VPS)** — até lá, o Telegram (que já funciona) entrega.

**Nota de contagem:** com o **#24 (agente de melhoria, C24)** adicionado na 4ª rodada, agora são **24 workflows numerados (1-24)**; "F" segue sendo a camada de superfícies, não um workflow. (Ver nota nº1 no fim.)

---

## 3. Tabela-resumo

Legenda — Esforço: **P** pequeno / **M** médio / **G** grande. Valor: contribuição pra dor nº1 (vazão/disciplina).

| # | Workflow | Superfícies | Depende de (cron/VPS? push? persistência nova?) | Esforço | Valor (vazão/disciplina) |
|---|---|---|---|---|---|
| A1 | Check-in matinal | app | cron leve; push in-app (dev build+VPS) | M | Alto (dá direção; abre o loop) |
| A2 | Encerramento 19h | app, Telegram | cron (19h) | M | Alto (planner≠executioner) |
| A3 | Fechamento noturno | app, Telegram, Obsidian | grava vault (aprovar); persiste scorecard | G | **Máximo** (fecha o loop do dia) |
| A4 | Review semanal | app, Obsidian | cron (dom); lê ClickUp+vault | G | **Máximo** (segura o sistema) |
| A5 | Reviews maiores | app, Obsidian | cron (mês); balanço patrimonial | M | Médio (estratégia, menos diário) |
| B6 | Captura universal | app | profile default; staging; hora-própria via scheduler (D18); cheatsheet | M | **Máximo** (a porta de tudo) |
| B7 | Sessão de leitura (áudio) | app, Obsidian | gravação nativa + transcrição; buffer local + autosave BFF; compilar→vault | G | Alto (lane #1) |
| B8 | Aprendizado→Anki | app, Obsidian, Anki | pipeline Leo-estuda→card; fila #anki/pending (W13) | P | Médio |
| B9 | Terapia | app, Telegram, Obsidian | garantia de privacidade | P | Médio (sensível, raro) |
| C10 | Motor de cobranças (unif.) | app, (Telegram transição) | **cron + VPS**; push in-app = dev build+VPS; unifica tarefa/financeiro/saúde/rotina | G | **Máximo** (o motor da disciplina) |
| C11 | Escalada + Mentor | app, Telegram | scorecard/histórico persistido | M | Alto (cobrança certa na hora certa) |
| C12 | Dashboard semanal | app, Obsidian | persistir tríade (rotina/sessão/tarefa) | G | Alto (número frio → ação) |
| C13 | Sincronização Anki | app, Anki | AnkiConnect (Anki aberto no PC); fila #anki/pending | M | Médio |
| C24 | Agente de melhoria (kaizen) | app | telemetria (sqlite local); lane batch; propõe-só (aprovação) | M | Médio (o sistema se conserta) |
| D14 | Tarefas por área | app | reestruturar p/ 8 áreas; staging+Aguardando; ligar staleness | M | Alto (o "onde eu mexo") |
| D15 | Saúde | app, Telegram | recorrências | P | Médio |
| D16 | Obrigações financeiras | app | recriar recorrências à mão (planilha=referência) | M | Alto (dor concreta, determinística) |
| D17 | Quarentena de ideias | app, Obsidian | acoplada ao A4 | P | Médio |
| D18 | Aguardando/delegações | app | lembrete de hora marcada (scheduler/VPS); staleness | M | Médio-alto (prazo-curto do trabalho) |
| D19 | Hierarquia de planos | app, Obsidian | formato/local no vault | M | Alto (**10a é este fim de semana**) |
| D23 | Sessões de foco | app, Garmin | timer; persistir sessão; Garmin | G | Médio-alto (3ª perna da tríade) |
| E20 | Mentor | app, Telegram | personality real; C11 | M | Alto (accountability) |
| E21 | Conselho + Decision Journal | app, Obsidian | Decision Journal no vault | P | Médio |
| E22 | Chat persistente | app | **persistência da conversa** | M | Médio (cockpit de conversa) |
| sub | Edificação (B9/A4/E20) | app, Obsidian | tag própria; agregação no review; Mentor acompanha | M | Alto (aprender→aplicar) |
| sub | Manual/SOP (transversal) | app | tooltips + diagramas dos SOPs (lane batch) | M | Médio (Leo é visual) |
| sub | Objetivos acumulativos (D19/C12) | app, Obsidian | acumulação diária (sqlite); dashboard publicável no GitHub | M | Alto (aderência ao macro) |
| sub | Calendário (Outlook+GCal) | app (Calendário) | Outlook read-only best-effort (fallback ICS); GCal OAuth (lê+insere) | M | Alto (agenda no cockpit) |

**Leitura rápida da tabela:** o **deep-dive priorizado pelo Leo é #6 captura → #3 fechamento noturno
→ #10-11 motor de cobranças** — é por onde discutir a fundo primeiro. Os grandes bloqueadores
compartilhados: **always-on (cron + VPS)** para digest/lembrete-na-hora (C10, A1, A4, D18) e para o
**push in-app** que o app-first exige (dev build + VPS; hoje morto no Expo Go); **persistência nova em
sqlite local** (scorecard/tríade/telemetria em C12/C11/D23/C24; conversa em E22 no Hermes); e a **lane
batch** (`claude`/`codex` no PC) que gera dashboard (C12) e roda o kaizen (C24). Enquanto o VPS não sobe, o Telegram cobre o aviso.

---

## 4. Notas de conflito entre os insumos

Onde as fontes divergem, o **INPUTS manda** (regra do briefing). Registrado para a spec resolver:

1. **Contagem de workflows (resolvida).** A seção 9 lista 23 numerados (1-23) + "F" (superfícies, não workflow). A 4ª rodada adicionou o **#24 (agente de melhoria, C24)** — agora são **24 workflows** de fato (1-24), e F segue como camada transversal.
2. **Horário do review semanal (resolvido 3ª rodada).** Travado em **domingo 20h**; o `CLAUDE.md` do vault (dom 22h) será corrigido na implementação. O mensal funde no 1º domingo.
3. **Duração vs horário do review.** INPUTS seção 6 escreve "review semanal dom 20min" (parece ser *duração* 20 min) e seção 5 "dom 20h" (*horário*). Provavelmente ambos: rito de ~20 min começando 20h.
4. **Momento do check-in matinal (resolvido 3ª rodada).** São **duas interações**: toque às 5h30 (guia a sequência do dia, anti-doomscroll) + check-in às 8h20 na mesa. Não é mais "5h30 vs 8h20".
5. **Profile default de captura descasado.** O as-built usa profile "Leitura" como default de captura (seção 4, "pontas soltas") — contradiz a lei nº2 (captura simples). Tratei como bug a corrigir (B6).
6. **Duas escalas de severidade divergentes.** `cadence.py` (back) vs re-parse no front (seção 4). Uma fonte só (C11 nº1).
7. **App-first vs "Telegram = canal #1" (D-14).** O INPUTS (2ª/3ª rodada) decide **app-first** (notificação primária no app); isso **supersede** a moldura do D-14 (Telegram como backbone/canal #1). Telegram = ponte de transição até o push in-app (dev build + VPS) existir — sem conflito de fluxo, só de ênfase histórica.
8. **Áreas: 8 vs 4+tags — a direção mudou entre rodadas.** A 1ª rodada sugeria manter 4 listas; da 2ª em diante o Leo confirma as **8 áreas** (pediu opinião sobre separar mapa-de-vida de listas operacionais). Apresentei o trade-off em W14 sem cravar, como o INPUTS pede.
9. **Persistência do scorecard mudou de recomendação.** Eu sugeria ClickUp (1ª/2ª rodada); a regra "sem SQL em nuvem" (4ª rodada) classifica o check-state (só a máquina lê) como → **sqlite local**. Ajustei A3/C12; a visão que o Leo lê continua no dashboard/vault.
10. **Punição (A3.3) — resolvido 6ª rodada.** Eu recomendei NÃO punir; o Leo pediu punição. TRAVADO: **pontos sobre as Conquistas N1-4** (furar desconta pouco, nunca vergonha — lei nº4 preservada); **stakes reais/anti-charity ficam FORA do v1**, só se o kaizen provar necessidade.
11. **Balanço patrimonial: mensal, não trimestral.** Eu sugeria ritual trimestral/anual; a 5ª rodada trava **mensal** (no review do 1º domingo). Ajustei A5.
12. **B7.1 persistência: minha 1ª recomendação era inviável.** "Append no vault a cada fala" = ~10s de commit por fala. Revisado para **buffer local + autosave no BFF (sqlite) + compilação única**. Vault recebe só no `compilar`.
13. **D16: recriar à mão, não importar.** Eu sugeria importar a planilha; a 5ª rodada trava **recriar as recorrências à mão** (planilha = referência de conferência).
14. **Triagem do staging: no ClickUp, não no app.** Minha modelagem sugeria triagem assistida no app; a 5ª rodada trava a triagem **dentro do ClickUp** (app só mostra "staging: N").
15. **Calendário Outlook — caveat técnico (6ª rodada).** O Graph API corporativo pode ser barrado (registro de app exige TI; a rede tem SSL interceptado). Especificado como **read-only best-effort com fallback** (URL ICS publicada / leitura best-effort). GCal (pessoal) via OAuth padrão, lê e insere. Registrado para a spec não assumir Outlook read/write garantido.
16. **"IA insere no GCal" estende a lei nº3 a eventos.** A escrita em calendário (só GCal pessoal) segue a regra "IA nunca grava sem aprovar": insere quando o Leo pede explicitamente ou confirma na captura.
