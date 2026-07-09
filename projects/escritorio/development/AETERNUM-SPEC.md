---
artifact: spec
capability: aeternum
status: v1-aprovada
date: 2026-07-09
normative: true
consolida: [AETERNUM-DESIGN-INPUTS.md, AETERNUM-WORKFLOWS-V1.md, DECISIONS.md, CAPTURE-GRAMMAR-SPEC.md, "vault CLAUDE.md"]
nota: >
  Esta é a spec NORMATIVA do Aeternum v1 (o contrato do que o sistema é e faz). O racional, os
  trade-offs e o histórico das 6 rodadas moram em AETERNUM-DESIGN-INPUTS.md e AETERNUM-WORKFLOWS-V1.md
  — referenciados aqui, não repetidos. Frases são testáveis ("o sistema faz X quando Y").
  Onde a spec cravou algo ainda vago, está marcado "(judgment call)".
---

# AETERNUM — Spec v1 (normativa)

## 1. O que é / escopo

**Aeternum** é o command center pessoal do Leo: **app** (Expo/RN, Android-first) + **BFF** (FastAPI) +
**Hermes** (agente self-hosted) + **vault** (Obsidian em GitHub, `LeonardoLifeMain`) + **ClickUp**.
Um só sistema, uma só memória de vida. v1 é **conceitual-completo**: define comportamento observável,
dados e superfícies; não é plano de implementação (ver §9).

O sistema existe para resolver a **dor nº1 do Leo — vazão + disciplina**: ele já captura em muitos
lugares e para porque nada reaparece. O Aeternum fecha o loop **capturar → triar → executar → ser
cobrado → refletir → planejar**, e a IA fecha o loop de reflexão **por ele**.

**Fora de escopo (v1), explícito:**
- **Vestra / AeternumFintech (ConsigVerse)** — só citada como pilar no plano macro; não é gerida aqui.
- **Anti-charity / stakes financeiros reais** — fora do v1; só entram se o kaizen (C24) provar que os pontos não bastam.
- **Banco SQL em nuvem** — proibido (§3). Persistência de máquina = sqlite local.
- **WhatsApp e e-mail/Outlook-como-caixa** — fora; Outlook entra só como **calendário read-only** (§3).
- **Garmin como app completo** — é **satélite** (alarmes/timers/vibração), não uma superfície de trabalho.
- **Voz de captura curta via Wispr para leitura** — substituída por gravação de áudio nativa na sessão (B7).

---

## 2. As 9 leis (normativas)

O sistema DEVE respeitar, sem exceção:

1. **Vazão antes de captura.** Todo item capturado tem destino, reapresentação ou morte digna. Nada some sem um dos três.
2. **Captura nunca exige decisão.** A captura é um campo (voz ou texto); a inteligência mora na triagem, não na captura.
3. **A IA nunca TRANSFORMA sem aprovação explícita do Leo** — nota estruturada, diário, evento de calendário. A IA estrutura e propõe; o Leo aprova. **Enviar a captura JÁ É a aprovação para o Raw** (verbatim, imutável — raw-first do contrato do vault); bloquear a captura violaria a lei 2. O gate explícito cobre a transformação, não o registro cru. Autoria preservada.
4. **Leis TDAH.** Campos fixos (nunca página em branco); gatilho por evento além de horário; check visível (dopamina); **jamais vergonha nem streak-reset** (dia quebrado = replanejar, "never miss twice", meta 20/30 não 30/30, piso mínimo de 5 min) — **desconto leve de pontos é permitido** (decisão explícita do Leo) apenas em **padrão** (≥3 furos), nunca furo isolado, com **teto semanal de desconto** e **linguagem 100% factual**; time-boxing (bloco 15-30 min > tarefa aberta); IA como body double.
5. **Contra o cemitério de planilhas.** O Aeternum é O lugar único; nunca exige que o Leo reconstrua estrutura.
6. **Cobrança por número frio.** Escalada suave→dura regulada por desvio mensurável (scorecard 12WY, meta ≥85%), não por humor. Nudge diário seco; **Mentor com voz só quando vira padrão**.
7. **Privacidade — notificações E artefatos publicados.** Notificação em lockscreen/preview NUNCA carrega conteúdo de nota sensível (identidade, saúde mental, terapia) — só chamadas neutras. **Artefato publicável (dashboard no GitHub) = apenas métricas não-sensíveis e agregadas** (rotina %, sessões, leitura, tarefas); saúde, terapia, Edificação, Self Honesty, psiquiatra NUNCA aparecem. Default = privado; publicação = **opt-in por seção**.
8. **Glass, not store.** O app não guarda dado canônico. ClickUp = tarefas; vault = conhecimento/reflexão; Hermes = memória do agente.
9. **Senhas ficam fora** do sistema de captura.

---

## 3. Arquitetura

### Superfícies
- **App (Expo/RN, Android-first) = superfície primária.** O Leo abre, opera e é avisado por aqui. É vidro sobre o Hermes; não guarda dado canônico.
- **Obsidian (vault em GitHub) = home de conhecimento/reflexão.** Escrita via GitHub MCP, **sempre após aprovação** (lei 3).
- **Garmin = satélite.** Alarmes de rito, timers de bloco, vibração do toque das 5h30. Concilia com o sistema via log; não é app completo.
- **Telegram = secundário / ponte de transição.** Cobre notificação enquanto o push in-app não existe (§9 P1→P2). Depois, opcional (rua/fallback), nunca obrigatório.
- **Calendário (superfície nova no app) = agenda agregada.** Visão dia/semana juntando **Outlook** (profissional, **read-only best-effort**), **Google Calendar** (pessoal, **read/write**), itens de hora marcada (D18/B6) e ritos (A1/A2/A3).

### Homes de dados (glass-not-store)
- **ClickUp** = TODAS as tarefas (estrutura em §8).
- **Vault** = conhecimento, reflexão, diário, identidade, leituras, ideias, fechamentos, Conquistas N1-4, SOPs, hierarquia de planos, cards `#anki/pending`, Edificação, terapia.
- **Anki** = flashcards / repetição espaçada (dono da retenção dura).
- **Hermes memory** = memória do agente, contexto conversacional, personalidades.
- **sqlite local** (BFF) = **só o que a máquina lê**: checks de rotina, sessões, telemetria, device tokens, log de notificação, buffer de leitura, cache/dedupe. Hoje no PC, depois no VPS.
- **Calendários** = fonte externa (Outlook RO, GCal RW). Nada canônico no app.

**Regra de persistência (normativa):** se o **Leo lê** um dado → vault (markdown/dataview) ou ClickUp.
Se **só a máquina lê** → **sqlite local**. **SQL gerenciado em nuvem é proibido** no v1 (single-user).

### Duas lanes de modelo
- **Hermes (interativo, diário)** = captura, chat, cobrança, ritos. Engine sempre-ligado.
- **Batch pesado (`claude` CLI + `codex` CLI, OAuth das assinaturas, no PC do Leo)** = jardinagem do vault, sugestão de links/Anki, geração de dashboard (C12) e o kaizen (C24). Roda em cron de FDS/madrugada; **nunca embute OAuth no app/BFF**.

### Caminho crítico
Push in-app confiável, lembrete de hora marcada e digest matinal **exigem dev build (não Expo Go) + VPS always-on**. Até isso existir, o Telegram entrega e o PC hospeda o cron (§9).

---

## 4. O dia (dois templates + timeline travada)

O sistema oferece **dois templates de dia editáveis**; o toque das 5h30 (A1a) pergunta qual é o dia:

**DIA YOGA:** 5h30 acordar → yoga → meditação → rotinas (skincare) → academia 1h → escritório ~8h.
**DIA CORRIDA:** 5h30 acordar → rotinas → **academia adiantada** → **corrida 30min (SEMPRE depois da academia)** → escritório ~8h30.

Timeline travada (horários são default editável; a estrutura é normativa):

| Hora | Bloco | Rito/workflow | Superfície |
|---|---|---|---|
| 5h30 | acordar | **A1a** toque (alarme/checklist, guia o template do dia) | app + Garmin (vibra) |
| manhã | rotinas + treino (+corrida no dia corrida) | scorecard (A3) + W23 (treino/corrida = sessão) | app/Garmin |
| ~8h/8h30 | chega à mesa | **A1b** check-in (agenda do dia, prioridade #1, estado, marca rotinas) | app |
| ~8h30 | jornal | captura solta (B6) | app |
| ~9h | organizar cobranças | **C10** digest | app (Revisão) |
| 9h30 | daily ITER | — | — |
| dia | blocos deep/shallow | **C11** timers (Garmin) + **W23** + triagem do staging **no ClickUp** | Garmin + ClickUp |
| **19h** | **Shutdown (A2)** | fecha trabalho, follow-ups (D18), plano de amanhã, "staging: N" | app |
| noite | estudo/projeto ou pessoal | W23 · B7 (leitura) · B8 (Anki) · D15 | app/Garmin |
| ~21h | **fechamento noturno (A3)** | diário→IA→aprova, destaque ressurgido, scorecard | app |
| 21h30 | deitar → ler 22h30 | **B7** sessão de leitura (áudio) | app |
| dom 20h | **review semanal (A4)** (travado) | scorecard %, esvaziar ideias, Rerise, temas da semana | app |
| **1º dom do mês, 20h** | **review mensal (A5)** FUNDIDO ao semanal | síntese mensal + **balanço patrimonial** | app + vault |
| FDS/madrugada | batch | jardinagem, dashboard (C12), kaizen (C24) | PC (lane batch) |

**Modo mínimo vs pleno (carga ritual declarada).** O **dia válido mínimo** = A1b em ~60s (ver a prioridade nº1) + A3 em ~90s (1 linha de diário por voz + os checks); todo o resto (destaque ressurgido, Self Honesty, sessões, digest detalhado) é **enriquecimento opcional**. Overhead: **modo mínimo ≈ 3 min/dia**; **modo pleno ≈ 30-40 min/dia** — dos quais o **Shutdown (15-30 min) substitui a revisão das 19h que o Leo já fazia/queria** (não é overhead novo). Leitura noturna e timers são **atividades do Leo, não custo do sistema**.

---

## 5. Os 24 workflows (forma normativa)

Numeração canônica (o "W" e o índice de categoria são estáveis). Cada um: gatilho → comportamento observável → notificação → destino dos dados.

### A — Ritos

**A1 · Check-in matinal (duas interações).**
O sistema DEVE disparar (a) às **5h30** uma **tela de alarme/checklist** que guia a sequência do dia pelo template escolhido (Yoga/Corrida), sem feed nem decisão, e vibrar no Garmin; e (b) às **8h20** (ou ao chegar à mesa) um **check-in** com 3 prompts fixos (foco · estado energia/clareza **perguntado** · o que não pode furar) **+ resumo da agenda do dia** (agrega Outlook+GCal+hora-marcada+ritos). O sistema puxa as 3 prioridades do dia do ClickUp (due=hoje + piso de rotinas). Rotinas concluídas marcam o scorecard (sqlite). **Piso mínimo:** o A1b em ~60s = ver a prioridade nº1 e confirmar (estado e agenda são enriquecimento). **Notifica:** empurrão às 5h30; lembrete leve se não houve check-in até 9h. **Dados:** estado e prioridades ficam em estado leve (sqlite); nada no vault.

**A2 · Shutdown — encerramento do trabalho (19h).**
Às 19h o sistema abre um checklist fixo: pendências, follow-ups a cobrar (D18), plano de amanhã (3 prioridades que pré-carregam o A1b), e o contador **"staging: N itens" (com a idade do mais velho)**. A **triagem do staging acontece no ClickUp** (o app não tem UI de triagem), mas o Shutdown oferece **triagem em lote assistida** (a IA propõe o destino de todos, o Leo aprova em bloco). **Notifica:** empurrão às 19h; se pulado, reaparece amanhã mais firme (C11), nunca envergonha. **Dados:** complete/reschedule → ClickUp; plano de amanhã → estado leve.

**A3 · Fechamento noturno.**
Ao fim do dia (evento ~21h) o Leo despeja o dia em 1 campo; o Hermes estrutura como `diario` e **mostra para aprovação** antes de gravar. O sistema reapresenta **1 destaque + pede 1 frase de aplicação** (dose diária) e mostra o **scorecard de rotinas** (binário). **Piso mínimo:** o A3 em ~90s = 1 linha de diário por voz + os checks (destaque e Self Honesty são enriquecimento opcional). **Notifica:** empurrão seco; furos viram cobrança só por padrão (C10/C11). **Dados:** raw imutável + nota `Daily/YYYY-MM-DD.md` no vault **após aprovar**; check-state em sqlite; visão no dashboard.

**A4 · Review semanal (domingo 20h, travado).**
O Hermes **pré-gera** `Fechamentos/Weekly/YYYY-WW.md` (resumo, padrões, conquistas, travas, ideias a graduar, foco) lendo os arquivos da semana; o Leo aprova/corrige. O sistema calcula o **scorecard % (12WY, ≥85%)**, esvazia o **inbox de ideias** (D17), decide **1 rotina nova (Rerise, gated: só se as vigentes ≥85%)**, e registra os **temas da semana** (eventos dia+hora → plano + lembrete na hora). No **1º domingo** funde com o A5. **Notifica:** empurrão de domingo; 2 semanas puladas → Mentor. **Dados:** vault (após aprovar) + scorecard (sqlite).

**A5 · Reviews maiores (mensal / 12 semanas / anual / 10 anos).**
No **1º domingo do mês** (sessão estendida do A4, um rito só) o Hermes gera a síntese mensal e apresenta o **balanço patrimonial mensal** (ativos/passivos/PL). O trimestre é o **ciclo de 12 semanas (12WY)**, não trimestre-calendário. Cada nível revisa o de cima (dia→semana→mês→12s→ano→10a). **Calendário operacional:** semana **ISO (seg-dom)**, review dom 20h; **mês civil** (financeiro/patrimônio); **ciclo 12WY** com datas próprias de início/fim. **Precedência no 1º domingo:** semanal+mensal fundidos; se coincidir com fechamento de ciclo, o **fechamento de ciclo absorve os dois** (uma sessão só, mais longa). **Notifica:** início do mês; **desvio do plano macro** → Mentor. **Dados:** vault (hierarquia de planos, W19).

### B — Entradas

**B6 · Captura universal.**
A captura pelo **app é primária** (voz Wispr ou texto), um campo, zero categoria na hora. O Hermes detecta o modo por palavra-chave; sem palavra = `captura` → **Raw** imutável (**enviar já é a aprovação para o Raw**, lei 3 — o gate explícito vale só para transformações). Tarefa pessoal → ClickUp (Leo confirma o destino). Tarefa de trabalho no correr do dia → **lista Staging** (triada depois no ClickUp). O sistema distingue **"minha tarefa"** de **"cobrar Fulano de Y às 14h"** (keywords "cobrar"/"funcionário" + nome/hora). **Ambiguidade COM hora do mesmo dia** ("João 14h") → vira **"pendente de confirmação"**: 1 notificação de 1 toque imediata ("cobrar o João OU tarefa tua?"); **se não confirmado até a hora, dispara lembrete genérico mesmo assim** (não silencia). A captura em si nunca exige decisão (lei 2). **Captura com hora própria** ("entregar às 15h") usa o **scheduler de hora marcada** (D18). Resposta seca "✅ anotado". Um **cheatsheet** no app lista modos/palavras-chave. **Dados:** Raw no vault; tarefas no ClickUp; pendências de confirmação em sqlite (scheduler).

**B7 · Sessão de leitura (áudio contínuo).**
Abrir a sessão (`livro: título, página`) inicia **gravação de áudio contínua com transcrição nativa** no app (não Wispr). **Hooks falados:** "quote" → citação **verbatim**; "comentário"/"comentários Leo" → pensamento dele; demais modos por palavra-chave. A sessão é **cronometrada**: gera log `{livro, duração, páginas, notas}` (sessão = duração, integra W23/C12). **`compilar`** finaliza: **uma** chamada Hermes vira **nota estruturada no vault**; `lista` → ClickUp (compras); a IA sugere candidatos a Anki. **Persistência:** buffer local + autosave no BFF (sqlite) durante a sessão; **o vault recebe só na compilação**. **Fila de sessões não compiladas:** se o `compilar` falhar (Hermes caído/app fechado), a sessão fica **pendente** e é **reapresentada** (badge + item no A3/A4) até compilar ou descartar — nada se perde. **Notifica:** resurfacing (A3), não cobrança.

**B8 · Aprendizado / estudo → Anki.**
Captura de conceito → Raw; o Leo **revê/estuda** e aprova a nota `conhecimento` (ordem: captura → estuda → Obsidian → só então card). O card usa o **template Frente / Meaning / Example / Hook** (a IA preenche os 4, Leo aprova) e entra na fila `#anki/pending` com **deck sugerido por domínio** (§8). **Notifica:** lembrete leve de revisão (não cobrança). **Dados:** nota no vault; card no Anki (C13).

**B9 · Terapia (+ sub-workflow Edificação).**
Captura `terapia` → reflexão **marcada como sensível** (schema `mode=reflexao, sensitive=true, sensitive_reason=terapia`, não silo novo); **nunca** aparece em preview nem em artefato publicado (lei 7). Sintoma/compromisso → ação (tarefa Saúde, D15). O **Decision Journal não inclui terapia**.
**Sub-workflow Edificação (atravessa B9/A4/E20):** o sistema registra continuamente aprendizados sobre si (defeitos, hacks, insights) com tag própria; no review (A4/A5) a IA **agrega "o que você aprendeu sobre si" e propõe um plano de prática**; o **Mentor (E20) acompanha a aplicação** (hack vira lembrete/rotina; aderência entra no scorecard). **Dados:** vault (sensível) + scorecard.

### C — Motores

**C10 · Motor de cobranças (unificado).**
Cron diário (~9h) seleciona, por regras determinísticas (`cadence.py`), o que precisa de ação de **todas as fontes: tarefas + financeiro + saúde + rotinas/exercícios furados**. Cobra se **atrasada**, **vence hoje..+N** ou **parada ≥N dias**; nunca cobra item fechado. **Rotina furada entra por PADRÃO, não por furo isolado** (default ≥3 furos). Monta **um** digest ordenado por urgência, entregue **no app** (Telegram na transição). O **staging que envelhece** além do limiar config também entra no digest ("staging: N itens, mais velho Xd") — pra não virar inbox morto. **Notifica:** 1 digest/dia, seco, preview neutro. **Dados:** leitura de ClickUp + scorecard (sqlite); nenhum dado novo canônico.

**C11 · Escalada de tom + Mentor-quando-vira-padrão.**
Cada item ganha tom pela idade do atraso: **🟡 no prazo · 🟠 leve (1-2d) · 🔴 firme (3-6d) · 🚨 urgente (7+d)** (fonte única: back-end; o front só exibe). O nudge diário é seco. O **Mentor entra com voz só quando vira padrão** (default: 3+ furos na mesma rotina, pendência >7d, ou scorecard <85%), para qualquer tipo do motor. **Punição harmonizada:** desconto **leve** de pontos (Conquistas N1-4) só em **padrão** (≥3 furos), nunca furo isolado, com **teto semanal** e linguagem factual; jamais vergonha/streak-reset. O **kaizen (C24) monitora**: se o desconto correlacionar com abandono, propõe removê-lo. **Notifica:** marcador no digest; fala do Mentor = evento raro, privado (nunca expõe tema sensível).

**C12 · Dashboard semanal.**
Gerado no A4 (e consultável sempre), agrega a **tríade: rotina=binária, sessão=duração, tarefa=entrega**, mais quantified-self, **scorecard % + Self Honesty + aderência a objetivos acumulativos (D19)**. A geração pesada roda na **lane batch**; o estado mora em sqlite; a exibição no app/vault. O dashboard é **publicável no GitHub — mas só as métricas não-sensíveis e agregadas** (rotina %, sessões, leitura, tarefas); saúde/terapia/Edificação/Self Honesty/psiquiatra ficam **só no dashboard privado** (app/vault local). **Default = privado; publicação = opt-in por seção** (lei 7). **Notifica:** nenhuma direta (alimenta o C11).

**C13 · Sincronização Anki (AnkiConnect).**
Cards aprovados entram na fila `#anki/pending` (vault); quando o **Anki desktop está aberto**, o sistema sincroniza via **AnkiConnect** (Leo aprova o lote); `.apkg`/TSV é fallback. Sincroniza oportunístico (âncora domingo 20h30) + varredura no A4. **Fila com limite configurável:** ao estourar, aviso no A4 + **oferta de degradação (export TSV em 1 toque)** — a fila nunca cresce silenciosamente. **Notifica:** lembrete leve quando a fila cresce. **Dados:** card no Anki; tag atualizada no vault.

**C24 · Agente de melhoria (kaizen).**
Observa o uso (capturas não triadas, nudges ignorados, ritos pulados, atritos) via **telemetria em sqlite**; a análise roda na **lane batch**; **1x/mês** entrega uma **proposta consolidada** de ajustes no review estendido (A5). **SEMPRE propõe, nunca aplica** (lei 3 estendida ao próprio sistema). **Notifica:** só no rito mensal. **Dados:** só metadados de uso — **nunca conteúdo** de captura sensível (lei 7).

### D — Gestão

**D14 · Tarefas por área.**
O app lista tarefas agrupadas pelas listas do ClickUp — **8 áreas de vida + Trabalho (ITER) + Staging** (10 listas), com **Aguardando** como tag transversal (§8); criar/concluir/editar/filtrar + recência. **Triagem do staging = no ClickUp** (a IA salva lá; o Leo/agente promove em lote). **Dados:** round-trip ClickUp. **Notifica:** nenhuma direta (cobrança é o C10).

**D15 · Saúde.**
Captura de sintoma/lembrete → tarefa acionável em **ClickUp/Corpo** (saúde física; Saúde Mental quando for o caso) — marcar médico, comprar remédio; não diagnostica. Médicos recorrentes (dentista 6/6m etc.) = tarefas recorrentes cobradas pelo C10. **Notifica:** via digest, sempre neutra (sensível). **Dados:** ClickUp.

**D16 · Obrigações financeiras recorrentes.**
As recorrentes (8 cartões + Unimed + condomínio, ~10 boletos/mês, NFs, IR) são **recriadas à mão no ClickUp** (a planilha Pagamento Mensal.xlsx é **referência de conferência**, não fonte de import). IR = checklist no ClickUp + SOP no vault. **Notifica:** via digest, cobrança limpa. **Dados:** ClickUp/Finance.

**D17 · Quarentena de ideias.**
`ideia` → `1- Inbox/Ideias/` com tag `#idea/graduating`. **A captura de ideia NUNCA é bloqueada** (lei 2). No A4, cada ideia vira projeto, knowledge, fica ou morre — **graduação no app (1 toque)**, a IA escreve no vault. **Degradação (A4 pulado):** o digest de segunda mostra **"review pulado + N ideias aguardando"** e oferece um **review mínimo de 5 min** (matar/graduar só o **top 5 pré-selecionado pela IA**). **Dados:** vault.

**D18 · Aguardando / delegações (+ scheduler de hora marcada).**
Follow-up "aguardando [pessoa]" → tag/status no ClickUp. **Dois relógios:** (a) espera de fundo → digest quando passa do prazo; (b) **hora dura** ("entrega às 14h") → **lembrete pontual na hora** via scheduler (também usado por B6/A4). Itens de hora marcada aparecem na superfície de **Calendário**. **Notifica:** in-app na hora; espera de fundo via digest. **Dados:** ClickUp + scheduler (sqlite).

**D19 · Hierarquia de planos (+ objetivos acumulativos).**
Cadência **dia → semana → mês → 12 semanas → ano → 10 anos**, notas linkadas no vault (dataview). **Objetivos acumulativos** (ex.: "academia este ano"): o input diário acumula (sqlite) e **todos os níveis de review mostram um dashboard de aderência** ao objetivo macro, publicável no GitHub (lane batch) — **só métricas não-sensíveis, opt-in por seção** (lei 7). **Notifica:** desvio do macro → Mentor. **Dados:** vault + sqlite.

**D23 · Sessões de tempo focado.**
Timer ao vivo (app/Garmin) OU log por voz a posteriori → sessão `{projeto, categoria, duração}`. Metas de X h/mês por categoria; leitura conta por projeto E categoria. É a 3ª perna da tríade (C12). **Notifica:** interstitial journaling opcional, só por timer. **Dados:** sessões em sqlite; agregação no dashboard.

### E — Conversa

**E20 · Mentor.**
Personality Hermes (real, não só "chapéu") que entra pelo C11 ou sob demanda; puxa scorecard + plano macro + notas; fala firme não-bajuladora, **fecha com uma ação** (tarefa ClickUp), respeita privacidade, e **acompanha a Edificação**. **Notifica:** único que "fala com voz" — raro, deliberado.

**E21 · Conselho + Decision Journal.**
Modo Conselho oferece perspectivas para **decisões pessoais** (trabalho fora); a decisão + racional viram entrada de Decision Journal no vault (após aprovar), revisada em A4/A5. **Dados:** vault.

**E22 · Chat persistente (+ chats por área).**
Chat estilo Codex/Claude que **persiste** (Hermes memory é dono; BFF reflete sessão/ID). A **UI mostra chats separados por área da vida**, mas por baixo é **um agente só (Mentor) com contexto de área** — não N personas; uma área **gradua para persona própria** só se acumular material/uso real. **Regra de promoção:** a conversa é **memória não-canônica** (Hermes memory); vira **vault/tarefa apenas por ação explícita** (o Leo pede "salva isso", ou a IA sugere e o Leo aprova — lei 3). O backup do estado do Hermes entra no **P2 (VPS)**. **Dados:** Hermes memory.

### Comportamentos transversais

**MODO RETORNO (≥7 dias sem interação).** Quando o sistema detecta ≥7 dias sem interação, a **primeira interação NÃO mostra a pilha acumulada** — mostra a tela **"voltar hoje"**: 3 ações, 5 minutos, piso mínimo, **digest zerado para hoje** + as **3 pendências mais críticas**. O sistema **nunca tenta reconstruir as semanas perdidas** ("never miss twice", não reconstrução). O **Mentor dá boas-vindas, não bronca**.

**MODO MÍNIMO DIÁRIO.** Ver §4: o dia válido mínimo = A1b ~60s + A3 ~90s (≈3 min/dia); tudo além é enriquecimento opcional. O sistema nunca trata o modo mínimo como furo.

### Sub-workflows nomeados (recapitulação)
- **Edificação** (B9/A4/E20): aprender sobre si → agregar no review → Mentor cobra a aplicação.
- **Manual/SOP** (transversal, §7): tooltips + diagramas dos fluxos renderizados dos SOPs do vault.
- **Objetivos acumulativos** (D19/C12): acumulação diária → dashboard de aderência publicável.
- **Calendário** (transversal, §3/§7): agenda agregada Outlook-RO + GCal-RW + hora-marcada + ritos.

---

## 6. Matriz de notificação

Canal primário = **app (push in-app)**; **Telegram** cobre a transição (P1) e vira fallback. Preview
**sempre neutro** para conteúdo sensível (lei 7). Limiares default são **config** (§8).

| Evento | Canal | Tom | Escalada |
|---|---|---|---|
| Toque 5h30 (A1a) | app + Garmin (vibra) | alarme neutro | — (é gatilho de rotina) |
| Check-in 8h20 ausente até 9h | app | lembrete leve | 3 dias sem check-in → Mentor |
| Digest de cobranças (C10, ~9h) | app / Telegram | seco, 1/dia | tom por atraso: 🟡→🟠(1-2d)→🔴(3-6d)→🚨(7+d) |
| Rotina furada | (entra no digest) | seco | **só por padrão** (≥3 furos) → desconto leve de pontos + Mentor; nunca furo isolado |
| Shutdown 19h (A2) | app | neutro | pulado → reaparece amanhã mais firme |
| Fechamento noturno 21h (A3) | app | seco | 3 furos seguidos de rotina → Mentor |
| Hora marcada (D18/B6) | app (in-app, na hora) | pontual | — |
| Compromisso vencido sensível (ex.: psiquiatra) | app | neutro/privado | cobra a ação, nunca o tema |
| Review semanal domingo (A4) | app | convite | 2 semanas pulado → Mentor |
| Desvio do plano macro (<85%) | app | Mentor com voz | é o próprio gatilho de escalada |
| Fila Anki cheia (C13) | app | lembrete leve | estoura limite config → aviso no A4 + export TSV 1-toque |
| Proposta kaizen (C24) | app (rito mensal) | sugestão | nunca cobra |
| Retorno (≥7d sem interação) | app | boas-vindas (Mentor), **sem pilha** | tela "voltar hoje": 3 ações/5min, digest zerado + 3 pendências críticas; nunca reconstrói |

Regra normativa: **um** digest calculado uma vez por dia (fonte única); nenhuma notificação por intervalo fixo; nenhuma que envergonhe (lei 4).

---

## 7. Telas do app (delta vs as-built)

As-built: Home, Capturar, Tarefas, Chat, Revisão (design v2 "midnight desk", contra mock). Deltas normativos:

- **Home / check-ins.** Home = "brief" com saudação por horário, estado (perguntado no A1b), 3 prioridades (do ClickUp), Radar (inbox/vencendo/nudge do Mentor). Delta: **tela de alarme A1a** separada (5h30, sem feed); estado e prioridades **reais** (hoje hardcoded).
- **Captura.** Um campo voz/texto. Delta: **modo sessão de leitura em áudio contínuo** com hooks falados e cronômetro (B7); **cheatsheet** de modos; corrigir o profile default.
- **Tarefas.** Delta: **10 listas** — 8 áreas de vida + **Trabalho (ITER)** + **Staging** (não as 4 atuais) + **Aguardando** (tag/status); editar; recência; o Shutdown mostra "staging: N".
- **Chat por área.** Delta: 2 colunas/drawer; **chats separados por área** sobre um agente só; persistência real (hoje decorativa).
- **Revisão.** Cobranças do dia por severidade (fonte única back) + itens ★ para Anki.
- **Calendário (NOVA).** Visão dia/semana agregando Outlook (RO) + GCal (RW) + hora-marcada + ritos.
- **Manual/SOP (NOVA).** Tooltips + **diagramas** dos fluxos, **gerados sob demanda da fonte (SOPs do vault) na lane batch, SEM rito de manutenção próprio** — atualizados só quando o kaizen mudar um fluxo. *(judgment call: renderização — imagem gerada no batch e embutida como asset; sem engine de diagrama no app.)*
- **Dashboard / scorecard.** KPIs da tríade + scorecard % + Self Honesty + aderência a objetivos acumulativos; cálculo no batch, estado em sqlite. **Privado por default;** o publicável (GitHub) leva só métricas não-sensíveis e agregadas, **opt-in por seção** (lei 7).

---

## 8. Contratos de dados

### Vault (alinhado ao `CLAUDE.md` do vault — não redefinir lá)
Raw-first: todo modo (exceto `diario`/`livro` que vão direto) grava o **Raw imutável** em `1- Inbox/Raw/` e a nota estruturada **linka de volta**. **10 modos**: `captura` (default), `diario`, `livro:`, `conhecimento`(+Anki), `reflexao`, `identidade`, `ideia`, `relacao`, `coach`, `empresa`. **`terapia` = flag de sensibilidade sobre `reflexao`** — schema único **`mode=reflexao, sensitive=true, sensitive_reason=terapia`** (não é 11º modo). *(Nota de implementação: o `CLAUDE.md` do vault hoje lista terapia como o 10º modo — atualizar para o schema de flag.)* Tag nova **`field/edificacao`** para o sub-workflow Edificação. To-dos NUNCA no vault. Citação sempre verbatim.

### ClickUp (estrutura final — normativa)
1 Space **Personal** (90133461895). **10 listas: Staging + Trabalho + as 8 áreas de vida.**
- **Staging** — intermediária, vida curta; recebe a captura de trabalho pré-triagem (B6); triada dentro do ClickUp (D14).
- **Trabalho (ITER operacional)** — **lista própria** para o dia a dia profissional: follow-ups de funcionários, entregas com hora, cobranças do daily.
- **8 áreas de vida** (o mapa-de-vida): **Corpo · Saúde Mental · Responsabilidade** (vida prática: housework, burocracia, compromissos pessoais) **· Finance · Carreira** (longo prazo: Vestra, network, saída, desenvolvimento) **· Estudo · Relacionamentos · Lazer**.
- **Aguardando = tag/status transversal** (não lista). Sessões de foco = custom fields `{categoria, duração}` OU time-tracking do ClickUp.

**Princípio (decisão das rodadas):** separar **mapa-de-vida** de **listas operacionais** — *"Carreira = pra onde vou; Trabalho = o que devo HOJE"*. O volume diário de follow-ups do ITER não pode poluir a visão de carreira de longo prazo; e **Responsabilidade** é vida prática, não "obrigações do trabalho".
**Migração do as-built:** Trabalho→Trabalho (mantém); Finanças→Finance; Saúde→divide Corpo/Saúde Mental na triagem; Pessoal→distribui nas demais na triagem. *(judgment call revisado pelo orquestrador: 10 listas confirmadas — Staging + Trabalho + 8 áreas.)*

### sqlite local (tabelas conceituais — só a máquina lê)
- `routine_checks` `{data, rotina, feito bool, template}` — scorecard (A1/A3/C10/C12).
- `sessions` `{id, tipo(foco|leitura|treino|corrida), projeto, categoria, inicio, fim, duracao, paginas?, livro?}` — W23/B7/C12.
- `telemetry` `{ts, evento, ref, meta_json}` — kaizen (C24), **sem conteúdo sensível**.
- `devices` `{token, plataforma, criado}` — push (já existe no BFF).
- `notif_log` `{ts, evento, canal, entregue}` — dedupe/auditoria de notificação.
- `reading_buffer` `{sessao_id, seq, hook, texto, ts, status(ativa|pendente|compilada)}` — autosave; sessões **pendentes** (compilar falhou) reaparecem no A3/A4 até compilar/descartar.
- `accum_goals` `{objetivo, nivel, unidade, incremento_diario, acumulado}` — objetivos acumulativos (D19).
- `scheduler` `{id, quando, tipo(minha|cobrar-terceiro), ref, disparado bool}` — hora marcada (D18/B6/A4).

### Anki
**6 decks por domínio:** Finanças & Investimentos · Direito · Tecnologia & IA · Pessoas & Comunicação · Mundo & Notícias · Vida & Mente. **Template Frente / Meaning / Example / Hook** (a IA preenche, Leo aprova; a IA sugere o deck). Mecanismo: **AnkiConnect** (Anki desktop no PC) + fila `#anki/pending` no vault; `.apkg`/TSV = fallback.

---

## 9. Sequenciamento conceitual (fases, não plano)

- **P0 — Correções (destravar o que já existe).** Corrigir o profile default (`Leitura`→captura); severidade com **fonte única no back** (front só exibe). *Justificativa: custo ~zero, remove bug que contamina captura e cobrança.*
- **P1 — Loop mínimo no PC (ataca a dor nº1 já).** Captura real → vault; fechamento noturno (A3) com aprovação; digest (C10) via **Telegram**; cron local no PC. **É best-effort enquanto o PC roda** (semântica de falha declarada na §10 — nada se perde). *Justificativa: o loop capturar→refletir→ser cobrado engata sem esperar VPS — é o que o W27 provou faltar.*
- **P2 — Always-on (VPS + dev build).** Push in-app; **lembrete de hora marcada**; **digest matinal** com o PC dormindo. *Justificativa: tira a dependência do PC ligado e habilita cobrança na hora e o empurrão das 8h.*
- **P3 — Leitura-áudio + Anki + sessões/timer.** B7 (gravação nativa), C13 (AnkiConnect), D23 (timer/log). *Justificativa: a lane #1 (leitura) e a retenção dura, que exigem gravação nativa e Anki no PC.*
- **P4 — Medição e automelhoria.** Dashboards (C12) + objetivos acumulativos + kaizen (C24) + Garmin + calendários. *Justificativa: dependem de dados acumulados dos P1-P3; são a camada estratégica, não o loop diário.*

---

## 10. Riscos e mitigações

| Risco | Mitigação (normativa) |
|---|---|
| **Outlook corporativo barra a API** (Graph exige registro/TI; SSL interceptado) | Calendário Outlook é **read-only best-effort com fallback** (URL ICS publicada / leitura best-effort). GCal via OAuth padrão. A spec não assume Outlook read/write. |
| **Verbatim quebrado na transcrição** (STT reformula a citação) | No hook "quote", o sistema preserva o texto como veio; testar a engine; suportar marcador de fim de citação; em degradação, sinalizar "revisar citação". *(judgment call: engine de STT nativo a decidir no P3.)* |
| **Latência do Hermes (~10s por chamada)** | Captura é fire-and-forget (resposta otimista "✅ anotado"; buffer local). A leitura faz **1 chamada no `compilar`**, nunca por fala. |
| **OAuth de assinatura (codex/claude) é ToS-gray** | **Risco aceito pelo Leo.** Mitigação: a lane batch roda **binário oficial, na máquina do Leo**; nenhum token de assinatura no app/BFF (só API key com teto no engine). |
| **PC não é always-on até o VPS** | Telegram cobre o aviso; o digest matinal só é garantido no **P2**. Nada crítico depende do PC ligado após o P2. |
| **Anki só no PC** | AnkiConnect exige o Anki desktop aberto; a fila `#anki/pending` aguarda e sincroniza oportunístico. Revisitar se houver VPS. |

### Semântica de falha do P1 (best-effort sem VPS)
O P1 roda no PC do Leo; **nada se perde**, mas a entrega é best-effort até o P2. Telegram é o canal de aviso do P1.

| Falha | Comportamento | O que o P2 (VPS) resolve de verdade |
|---|---|---|
| Cron perdido (PC dormindo) | dispara no próximo wake/boot | digest matinal no horário, PC dormindo ou não |
| Hermes caído | captura **enfileira local no app** e reenvia com retry (nada se perde) | engine always-on; sem backlog |
| Digest não entregue | aparece na **próxima abertura do app** (aviso via Telegram) | push in-app confiável + entrega pontual |
| Lembrete de hora marcada | best-effort enquanto o PC roda | disparo pontual garantido na hora |

---

## 11. Métricas de sucesso do v1

Ancoradas no caso real (o **Review W27** teve 4 semanas com **zero** dado de execução — o loop nunca engatou). **4 semanas depois do P1 vivo**, o review semanal DEVE conter dados reais:

- **Daily preenchido ≥ 20/28 dias** (meta 20/30 do próprio Leo). *(judgment call no denominador: 28 = 4 semanas.)*
- **≥ 1 captura/dia** em média chegando ao vault/ClickUp.
- **Sessões de leitura registradas** (com duração) em ≥ metade dos dias de leitura.
- **Psiquiatra MARCADO** — o compromisso vencido vira tarefa fechada (caso de teste da escalada C11).
- **Scorecard rodando**: rotinas binárias persistidas e um **% semanal** calculado (mesmo que abaixo de 85%).
- **Critério de falha**: se esse review sair vazio como o W27, o v1 falhou na dor nº1, independentemente de features entregues.

---

## 12. Registro de decisões

Histórico completo e racional: **AETERNUM-DESIGN-INPUTS.md** (seções "Resoluções 3ª/5ª/6ª rodada") e **AETERNUM-WORKFLOWS-V1.md** (tabela "Status das decisões" + "Notas de conflito" nº1-16). Decisões estruturais herdadas: **DECISIONS.md** (D-1 a D-14). Contrato de captura: **CLAUDE.md do vault** + **CAPTURE-GRAMMAR-SPEC.md**.

**Reversões mais importantes ao longo das 6 rodadas** (rastreáveis nas Notas de conflito):
- **Punição** — de "não punir" para **desconto leve de pontos sobre Conquistas N1-4** (só em padrão ≥3 furos, teto semanal, linguagem factual, jamais vergonha/streak-reset; anti-charity fora do v1; kaizen remove se correlacionar com abandono).
- **Persistência** — de "ClickUp/append no vault" para **sqlite local** para tudo que só a máquina lê (scorecard, buffer de leitura).
- **Financeiro** — de "importar a planilha" para **recriar as recorrências à mão** (planilha = referência).
- **Triagem do staging** — de "UI no app" para **dentro do ClickUp** (o app só mostra "staging: N").
- **Superfície** — de "Telegram = canal #1" (D-14) para **app-first**, Telegram = transição.

**7ª rodada — pós-crítica adversarial (2026-07-09).** Crítica **GPT-5.5 xhigh**: **15 achados, 13 aceitos/adaptados, 2 rejeitados parcialmente** (bloqueio de captura na degradação da quarentena; contagem de carga ritual que somava atividades pré-existentes do Leo — leitura/timers). Todas as correções são normativas/failure-modes — **sem mudança de arquitetura nem de decisão do Leo**. Principais adições: lei 3 clarificada (Raw = aprovação; gate = transformação), lei 7 estendida a artefatos publicados, MODO RETORNO (≥7d ausente), MODO MÍNIMO diário (pisos + overhead ≈3 min/dia), semântica de falha best-effort do P1 (§10), fila de sessões de leitura não compiladas, staging que envelhece no digest + triagem em lote, ambiguidade-com-hora → pendente de confirmação, punição harmonizada (desconto leve só em padrão), fila Anki com limite + degradação TSV, regra de promoção do chat, calendário operacional (ISO/civil/12WY), schema único de terapia, Manual/SOP sob demanda sem rito de manutenção.
