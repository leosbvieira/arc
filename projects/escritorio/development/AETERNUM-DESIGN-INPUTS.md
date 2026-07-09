# Aeternum — Insumos de Design (2026-07-06)

Consolidação da sessão de brainstorming (entrevista com Leo + 5 investigações delegadas).
Alimenta o CATÁLOGO DE WORKFLOWS e depois a spec. Não é a spec.

**Nome decidido:** o sistema (app + BFF + Hermes + vault) chama-se **Aeternum** — mesmo nome do
vault pessoal (`leosbvieira/aeternum`, local `C:\Users\Leonardo\Documents\LeonardoLifeMain`).
Não confundir com `AeternumFintech/Aeternum` (fintech Vestra/ConsigVerse — fora de escopo,
no máximo mencionada no plano macro como pilar).

---

## 1. Leis de design (inegociáveis)

1. **Vazão antes de captura.** Leo já captura (WhatsApp consigo mesmo, 99 abas, bloco de notas);
   ele parou de anotar porque nada reaparece. Todo capturado precisa ter destino, reapresentação
   ou morte digna. Review W27 do vault: 4 semanas com ZERO dado de execução — o loop nunca engatou.
2. **Captura nunca exige decisão** (PDF Fluxo Captura & Execução). Um campo, voz ou texto.
   Inteligência mora na triagem, não na captura.
3. **A IA nunca grava no vault sem aprovação explícita do Leo** (diário/reflexão). IA estrutura,
   Leo aprova. Autoria preservada.
4. **Leis TDAH:** campos fixos, nunca página em branco · gatilho por evento, não só horário
   ("quando termino o jantar → fechamento") · check visível (dopamina) · JAMAIS streak punitivo —
   dia quebrado = replanejar, não envergonhar ("never miss twice", piso mínimo de 5 min, meta 20/30
   e não 30/30 — linguagem do próprio plano de 30 dias do Leo) · time-boxing (bloco de 15-30 min >
   tarefa aberta) · IA como body double/accountability externa.
5. **Contra o cemitério de planilhas** (metapadrão das planilhas do Drive): replanejar do zero é a
   procrastinação produtiva do Leo. O sistema é O lugar único; a IA fecha o loop de reflexão por ele;
   nunca exigir que ele reconstrua estrutura.
6. **Cobrança por número frio:** escalada suave→dura regulada por desvio mensurável (scorecard
   semanal estilo 12WY, meta ≥85%), não por humor. Notificação seca no dia a dia; **Mentor com voz
   entra quando vira padrão** (ex.: 3+ furos na mesma rotina, pendência >Xd, desvio do plano macro).
7. **Privacidade:** vault contém material sensível (identidade, saúde mental, terapia). Notificação
   em lockscreen/preview do Telegram NUNCA carrega conteúdo dessas notas — só chamadas neutras.
8. **Glass, not store:** app não guarda dado canônico. ClickUp = tarefas; vault = conhecimento/
   reflexão; Hermes = memória do agente. (Decisão antiga, confirmada.)
9. **Senhas ficam fora** do sistema de captura (password manager é outro produto).

## 2. Perfil e dia-alvo

- Leo: crédito/fundos (ITER, com daily 9h30 e funcionários), founder (Vestra), TDAH, memória fraca,
  autodescrito "robótico — preciso de SOPs, lembretes, diagramas", data-driven, ambicioso,
  psicólogo semanal. Compasso: liberdade > dinheiro, construção > acumulação, impacto > status.
- **Dia-alvo (aspiração atual, entrevista):** acordar 5h30 → yoga+meditação 30min (OU corrida em
  dias específicos, aí sem yoga) → rotinas matinais 15min → academia 1h → escritório 8h/8h30 →
  jornal 30min → organizar cobranças do daily 30min → daily 9h30 → blocos deep/shallow/reuniões →
  almoço 30min na mesa → **19h rito de encerramento** (30-60min: shutdown ITER, follow-ups, plano
  de amanhã — planner ≠ executioner) → casa: estudo/projeto paralelo OU pessoal (médico etc.,
  talvez 1 dia/semana fixo) → **fechamento noturno** → deitar 21h30, ler até 22h30, dormir.
- Rotinas desejadas: skincare AM/PM, academia, corrida (dias específicos), yoga, meditação, leitura
  noturna, anotação do dia, reflexão 15min, diário. Hoje: nenhuma consistente (relacionamento
  atrapalha; dormir fora quebra tudo). Doomscrolling na cama é território inimigo.
- Planilhas históricas mostram a mesma rotina-alvo há anos (acordar ~6h40, correr/academia,
  yoga+meditação, Anki+estudo, notícias, trabalho; noite: estudo→academia→journal→livro).
  Templates devem ser EDITÁVEIS — o horário muda, a estrutura persiste.

## 3. Taxonomia

- **8 áreas de vida** (planilha "Corona", estável há anos, ranqueável): 1 Corpo · 2 Saúde Mental ·
  3 Responsabilidade · 4 Finance · 5 Carreira · 6 Estudo · 7 Relacionamentos · 8 Lazer.
  Colapsam em 4 pilares: Saúde Física, Saúde Mental, Riqueza, Relacionamentos.
  Hierarquia quando detalha: Área → Sub → Item → To-Do.
- **ClickUp hoje:** 4 listas (Trabalho, Finanças, Saúde, Pessoal) — Space Personal 90133461895.
  DECISÃO ABERTA: manter 4 listas e usar as 8 áreas como tags/campos, ou reestruturar.
- **Tipos de captura reais do Leo:** livros a ler · quotes · pensamentos/insights sobre si ·
  observações de pessoas · ideias de startup · filosofias · tarefas (prof/pessoal) · lembretes ·
  saúde (médicos, exames, dores, esquecimentos) · aprendizado/estudar (→ Anki).
- **Vault CLAUDE.md = contrato de captura já existente (10 modos):** captura default, diario,
  livro:, conhecimento(+Anki), reflexao, identidade, ideia, relacao, coach, empresa, terapia.
  Raw-first: cru imutável em `1- Inbox/Raw/`, nota estruturada linka de volta. Templates em
  `99 - Meta/Templates/` (8). Tags `type/* field/* status/*`. To-dos → ClickUp, NUNCA no vault.

## 4. Estado as-built (resumo do inventário de código)

- App Expo/RN (Home, Capturar, Tarefas, Chat, Revisão) + BFF FastAPI (:8000) + Hermes CLI oneshot
  (`hermes -z`) + ClickUp REST. Default roda MOCK (`HERMES_MOCK=true`, `TASKS_SOURCE=mock`);
  caminho ClickUp real validado 2026-07-05.
- Endpoints: /auth/login, /capture (único canal → Hermes), /devices, /tasks (CRUD+complete+detail),
  /digest, /internal/notify, /internal/run-digest.
- **Pontas soltas:** sem cron (nada chama /internal/run-digest) · push morto no Expo Go (token null)
  · Chat sem persistência (CONVS hardcoded, "+Nova" decorativo) · Home energia/clareza hardcoded ·
  sessão de leitura local/efêmera, ★Anki é só sufixo de texto · staleness desligado
  (update_offset=None) · DUAS escalas de severidade divergentes (cadence markers vs re-parse no
  front) · capture default profile "Leitura" (descasado) · BFF_URL hardcoded.
- **Telegram gateway FUNCIONA** (@Suwkz_bot, só Leo, auto-start no boot) enquanto o PC roda.
  VPS decidido mas pausado; é o caminho para always-on (digest de manhã exige).
- Personalidades Hermes: tarefas, capturas, mentor, conselho (config.yaml); BFF só prefixa
  "chapéu" de modo no prompt (não troca personality real).

## 5. Vault (LeonardoLifeMain) — o que existe

- PARA numerado, ~67 notas: 00 Dashboard · 02 Personal (Identidade, Reflexoes, SOP×9,
  Fechamentos Daily/Weekly/Monthly, Health, Conquistas gamificadas N1-4) · 03 References
  (Leituras/Livros/Artigos — VAZIO hoje) · 04 Main Notes/Knowledge (+Anki) · 05 Projetos ·
  06 Empresa · 1- Inbox (Raw/Ideias/Brain Dump/Pendencias.md) · 99 Meta (Templates, System) · Daily.
- Plugins: dataview, homepage, obsidian-git. Convenções: `YYYY-MM-DD - Titulo.md`, Daily
  `YYYY-MM-DD.md`, Weekly `YYYY-WW.md`.
- **Plano 30 dias** (09/06→09/07 — VENCE EM 3 DIAS): hora marcada + piso mínimo + cobrança;
  metas 20/30 treinos, 22/30 noites até 22h30; estudo 2h/dia (bloco A acompanhar 30min, bloco B
  construir 1h30); check-in matinal ~8h20 e noturno ~21h; export Anki dom 20h30; review semanal
  dom 20h (JÁ auto-gerado no vault). Jogo grande: mês1 infra → mês2 público+network → mês3 vetor
  da próxima empresa.
- **Compasso** (`Identidade/2026-04-17 - Quem eu sou...`): driver = descoberta; recusou R$10M e
  R$30M; saindo da empresa atual; histórico sensível de saúde mental; 5 compromissos (inclui
  psiquiatra em 30 dias — **vencido há 22 dias**: caso de teste da escalada).
- Leo fará o **plano de 10 anos neste fim de semana** — a spec define onde mora e formato, para
  já nascer dentro do sistema. Cadência desejada: diário→semanal→mensal→trimestral→anual→10 anos.

## 6. Pesquisa (validações externas)

- Stack recomendado: rito matinal 3-5min (3 prompts fixos) · fechamento noturno 10-15min
  (shutdown → diário cru→IA→aprova → 1 destaque ressurgido + 1 frase de aplicação → scorecard de
  rotinas) · review semanal dom 20min (5 prompts + esvaziar inbox de ideias + scorecard %).
- IA-no-loop: **editor como default, socrático quando trava** (híbrido). Human-in-the-loop sempre.
- Resurfacing: dose diária pequena (estilo Readwise) acoplada ao rito; Anki real para
  memorização que merece. Leo USA Anki ativamente e tem template de card próprio.
- **Pipeline Anki refinado (2ª rodada):** (a) leitura — nem tudo vira Anki (ficção não);
  ao FIM de cada sessão (ou semanalmente) a IA SUGERE candidatos a card, e o Leo também pode
  marcar durante o raw note (a IA lembra depois); (b) aprendizado/estudo — captura → Leo
  REVÊ/ESTUDA → aí vai pro Obsidian → então vira card. Sempre com gate de aprovação.
  Mecanismo recomendado: **AnkiConnect** (API HTTP local do Anki desktop) enquanto o sistema
  roda no PC do Leo — cards ficam em fila no vault (#anki/pending) e sincronizam quando o Anki
  abre; export .apkg/TSV vira fallback. Revisita quando houver VPS.
- Interstitial journaling nas transições de bloco = opcional, só se disparado por timer.
- Quarentena de ideias (Someday/Maybe) só funciona com review semanal vivo; senão vira lixão.
- Decision Journal: SÓ decisões pessoais (trabalho fora, por decisão do Leo).

## 7. Planilhas do Drive (padrões a portar)

- Grade semanal time-blocked = artefato nº1 (aparece em 5+ planilhas) → vira template de dia.
- Quantified-self: peso, sono, passos, exercício, álcool, livros/páginas, journal-feito →
  métricas do dashboard semanal.
- **Rerise = onboarding progressivo de hábitos (1 novo/semana)** → feature de rollout das rotinas.
- Conquistas N1-4 (já no vault) + mecânica Recompensa/Punição (delta a considerar).
- "Self Honesty": nota subjetiva de satisfação por área no fechamento (complementa métrica fria).
- Ritual mensal: "todo início de mês, um sábado sozinho para refletir" com objetivos mensuráveis.
- **Pagamento Mensal.xlsx ATIVA** = checklist real de faturas/boletos (8 cartões + Unimed +
  condomínio, status Pago/Não Pago) → carga inicial do workflow de obrigações financeiras.
- Anual.xlsx = balanço patrimonial pessoal (ativos/passivos/PL/gastos planejados) → candidato a
  ritual trimestral/anual.
- Visão plurianual (2026 empresa cash-flow, 2027 estudo, 2029 empresa estratégica) → insumo do
  plano de 10 anos.

## 8. Novos requisitos da entrevista (não cobertos acima)

- **Obrigações financeiras recorrentes:** ~10 boletos/mês, emitir NFs, IR anual com season e
  checklist de documentos. Determinístico → motor de cobrança. Primeira carga real das listas.
- **Profissional DENTRO do Aeternum (confirmado 2ª rodada):** tarefas de trabalho capturadas
  durante o dia caem numa **lista intermediária (staging) no ClickUp**; o Leo tem **janelas de
  triagem** no dia para migrá-las às listas finais (um agente IA ajuda na triagem). EXCEÇÃO:
  itens de prazo curto (ex.: "funcionário combinou de entregar às 14h") ficam VIVOS na
  intermediária e o Aeternum lembra NA HORA — follow-up de curto prazo não espera triagem.
  Dois tipos de lembrete distintos: "eu preciso fazer X" ≠ "cobrar fulano de Y às 14h".
- **Motor de cobranças é unificado:** cobre tarefas ClickUp + obrigações financeiras + saúde
  + **rotinas/exercícios furados** — rotina quebrada entra na mesma régua de escalada
  (respeitando lei 4: replanejar, não envergonhar; a régua é padrão, não furo isolado).
- **Saúde como workflow:** médicos com frequência (dentista 6/6m etc.), exames, sintomas/dores
  registrados (não para diagnosticar; para gerar ação: marcar médico/comprar remédio),
  esquecimentos registrados.
- **#23 Sessões de tempo focado:** hobby/projeto (ex.: barquinho de madeira) + categoria de
  propósito (concentração/terapêutica) + duração. Metas de X horas/mês por categoria. Leitura por
  projeto E por categoria. Timer ao vivo (app/Garmin) + log por voz a posteriori. Migrar Excel
  do barquinho como carga inicial. Tríade de medição: rotina=binária, sessão=duração,
  tarefa=entrega — dashboard cruza as três.
- **Garmin:** satélite de alarmes/timers de bloco (não app completo).
- **Canais — APP-FIRST (decidido 2ª rodada):** o Leo quer fazer TUDO pelo app, inclusive
  receber notificações pelo app; Telegram vira canal secundário/opcional (não obrigatório no
  fluxo). Consequência técnica honesta: push de app exige dev build (não Expo Go) + backend
  always-on (VPS) — até isso existir, Telegram (que já funciona) cobre a transição.
  Primeira coisa que ele olha de manhã: celular (e relógio).
- Rito das 19h precisa de NOME (Leo achou "rito" ruim). Sistema = Aeternum (decidido).

## 9. Catálogo v0 (esqueleto aprovado como base de discussão)

A. Ritos: 1 check-in matinal · 2 encerramento do trabalho 19h · 3 fechamento noturno ·
4 review semanal · 5 reviews maiores (mensal/trim/anual/10a)
B. Entradas: 6 captura universal · 7 sessão de leitura · 8 aprendizado/estudo→Anki · 9 terapia
C. Motores: 10 cobranças/digest · 11 escalada de tom + Mentor-quando-padrão ·
12 dashboard semanal IA · 13 export Anki
D. Gestão: 14 tarefas por área · 15 saúde · 16 obrigações financeiras · 17 quarentena de ideias ·
18 aguardando/delegações · 19 hierarquia de planos · 23 sessões de tempo focado
E. Conversa: 20 mentor · 21 conselho+decision journal · 22 chat persistente
F. Superfícies: app, Telegram, Garmin, Obsidian, notificações.

## 10. Decisões abertas (para a spec)

1. Áreas: Leo inclina para MAIS áreas que as 4 listas atuais (as 8 da taxonomia dele).
   Aberto: mapeamento no ClickUp — 8 listas vs 4 listas+tags; e como Inbox/staging
   intermediária + Aguardando entram na estrutura.
2. Integração Anki: recomendação = AnkiConnect local + fila #anki/pending no vault
   (validar com Leo; export .apkg/TSV como fallback)
3. RESOLVIDA em direção: app-first (tudo pelo app, notificação pelo app; Telegram secundário).
   Aberto: sequenciamento técnico (dev build + VPS) e o que roda no Telegram na transição
4. Nome do rito das 19h (e nomes dos ritos em geral)
5. Formato/local da hierarquia de planos no vault (10a → ciclo 12s → semana → dia)
6. Timer de sessão: app, Garmin, ou ambos; como o Garmin conversa com o sistema
7. Recompensa/Punição: portar ou deixar só Conquistas N1-4
8. Estado (energia/clareza) da Home: perguntado no check-in matinal? inferido?
9. Chat: persistência onde (Hermes memory? BFF sqlite? vault?)
10. Como o app expõe os 10 modos de captura sem virar menu (lei nº 2)
11. **Chats por área da vida** (2ª rodada): Leo levantou 1 chat de IA por área (treinador,
    nutricionista, "cara de relacionamento" etc.). TENSÃO com a decisão de 2026-07-04
    (pesquisa: poucos modos sobrevivem, "persona zoos" morrem; advisors de saúde/fitness/
    finanças/relacionamento foram rejeitados por falta de material no vault + segurança).
    Caminho do meio a discutir: MESMO agente (Mentor) com CONTEXTO de área carregado —
    conversas escopadas por área, sem multiplicar personas.

**Deep-dive priorizado (confirmado pelo Leo):** #6 captura → #3 fechamento noturno → #10-11
motor de cobranças + escalada.

**Resoluções da 3ª rodada (2026-07-06):**
- Review semanal: **domingo 20h** (não 22h — corrigir o comando do vault na implementação).
- Review mensal: **primeiro domingo do mês** (funde com o review semanal daquele domingo numa
  sessão estendida — um rito só, não dois).
- Chats por área (#22): APROVADO o desenho "UI mostra chats separados por área; motor é um
  agente só (Mentor) com contexto da área; área gradua pra persona própria se acumular
  material/uso real".
- App-first (F): confirmado de novo pelo Leo.
- Áreas (#14): Leo confirmou as 8; pediu opinião sobre tirar/adicionar — ver recomendação na
  decisão aberta nº1 (separar mapa-de-vida de listas operacionais).
- **Check-in matinal = opção (b), DUAS interações:** toque às 5h30 ao acordar (guia da sequência
  do dia: yoga OU corrida → academia) + check-in às 8h20 na mesa (dia planejado, prioridade #1,
  marca rotinas feitas). Desenhar o toque das 5h30 pra NÃO puxar pra doomscrolling (formato
  alarme/checklist, não feed).
- **Camada BATCH de modelos pesados (4ª rodada):** interativo do dia a dia = Hermes (gpt-5.4).
  Trabalhos pesados (ex.: FDS — revisar/jardinar notas do Obsidian, sugerir links, candidatos a
  Anki, gerar dashboard) = `claude` CLI e `codex` CLI por OAuth das assinaturas, RODANDO NO PC DO
  LEO em batch — compatível com a decisão antiga "só binários oficiais usam OAuth, para batch na
  máquina dele". Vira uma lane própria na arquitetura (cron de FDS/madrugada).
- **Workflow NOVO #24 — Agente de melhoria (kaizen):** observa o uso do sistema (o que foi
  capturado, nudges ignorados, ritos pulados, atritos), e propõe melhorias periodicamente.
  Recomendação: sinais micro no review semanal + proposta consolidada 1x/MÊS (semanal viraria
  ruído). SEMPRE propõe, nunca aplica sozinho (aprovação do Leo). Telemetria = a mesma do
  dashboard.
- **Banco SQL em nuvem: NÃO (recomendação).** Single-user; "glass, not store". Regra de ouro:
  se o LEO lê → vault (markdown/dataview) ou ClickUp; se só a MÁQUINA lê (telemetria, devices,
  checks de rotina, sessões, log de notificações) → **sqlite local** (hoje no PC, depois no VPS —
  que já é "nuvem" o suficiente). SQL gerenciado em nuvem só se um dia houver múltiplos
  dispositivos escrevendo offline — não é o caso.

## Resoluções 5ª rodada (2026-07-09)

Refletidas no AETERNUM-WORKFLOWS-V1.md. TRAVADO = fechado pelo Leo; PENDENTE-CONFIRMAR = recomendado, aguarda o Leo.

**TRAVADOS:**
1. **Dois templates de dia** (timeline manhã + A1a). DIA YOGA: 5h30 acordar → yoga → meditação →
   rotinas → academia → escritório ~8h. DIA CORRIDA: sem yoga/meditação; academia adiantada;
   corrida 30min SEMPRE depois da academia → escritório ~8h30; jornal 8h30.
2. **A1.1** estado PERGUNTADO. **A1.2** tela simples de alarme. **A1a** vibra no Garmin (futuro
   mini-app Garmin de alarmes).
3. **A2 = "Shutdown"**. A2.2 janelas + varredura 19h. A2.3 dois ritos.
4. **Triagem do staging acontece NO ClickUp**: a IA salva na lista staging; o Leo promove/triata
   dentro do ClickUp (agente IA ajuda em lote). O app NÃO tem UI de triagem — o Shutdown só mostra
   "staging: N itens". (Afeta A2, B6, D14.)
5. **A5 balanço patrimonial = MENSAL** (entra no review do 1º domingo), não trimestral.
6. **C10.1/2/3 e C11.1/2/3** aceitas.
7. **C12, C13, C24, D14 (8 áreas), D15, D17, D18, D19, D23, E20, E21, E22** aceitas.
   **D16.1: RECRIAR as recorrências à mão** no ClickUp (não importar; a planilha vira referência de
   conferência). **D16.2** aceito.
8. **B6:** captura pelo APP é primária (não só Telegram). Captura com hora própria ("entregar às
   15h") usa o mesmo scheduler de hora marcada do D18 (vale para tarefa própria, não só follow-up).
   B6.1 aceito + tooltip/cheatsheet de palavras-chave/modos no app. B6.3: keywords "cobrar"/
   "funcionário", IA decide na dúvida.
9. **B7 REDESENHADO:** sessão de leitura = ÁUDIO CONTÍNUO no app com hooks falados ("quote" →
   citação verbatim; "comentário"/"comentários Leo" → teoria/entendimento; demais por keyword).
   Motivo: Wispr limita ~5min → gravação nativa + transcrição no app. Sessões CRONOMETRADAS: log
   {livro, duração, páginas, notas} → lista de sessões por livro (integra D23 e C12: sessão=duração).
10. **B7.1 (recomendação revisada):** buffer LOCAL PERSISTENTE no app + autosave periódico no BFF
    (sqlite, scaffolding) + "compilar" → 1 chamada Hermes → nota no vault. Vault recebe só na
    compilação. (A anterior — 1 commit/fala — era inviável.)
11. **Manual/SOP no app** (transversal): tooltips + DIAGRAMAS dos fluxos, idealmente renderizados a
    partir dos SOPs do vault. (Leo é visual.)
12. **B8.2 template de card = Frente / Meaning / Example / Hook** (a IA preenche, Leo aprova).
13. **B9:** B9.1 terapia = flag de sensibilidade sobre reflexão. B9.2 DJ sem terapia. NOVO
    sub-workflow **"Edificação"** (B9/A4/E20): registro contínuo de aprendizados sobre si → vazão
    semanal/mensal (IA agrega + propõe plano) → Mentor acompanha a aplicação (hack vira lembrete/
    rotina; aderência entra no scorecard). Motivo (Leo): "aprendo hacks mas esqueço de aplicar".
14. **A4 "temas da semana"** (evento dia+hora entra no plano E lembra no dia/hora) + **A1b resumo da
    agenda do dia** com horários.
15. **D19/C12 "objetivos acumulativos"** (input diário acumula; todos os níveis de review mostram
    dashboard de aderência ao objetivo macro; publicável no GitHub, gerado na lane batch).

**PENDENTES-CONFIRMAR (recomendado, aguardando Leo):**
- **A3.1** scorecard: dado cru em sqlite + visão no app/dashboard.
- **A3.3 PUNIÇÃO** (Leo pediu): sistema de PONTOS sobre as Conquistas N1-4 (fazer ganha, furar
  desconta pouco; scorecard <85% já é a dor + Mentor); linguagem nunca de vergonha; anti-charity/
  stakes reais só se o kaizen provar que pontos não bastam.
- **A4.2** Rerise gated pelo scorecard (só sobe rotina nova quando vigentes ≥85%).
- **A4.3** graduação de ideias no app (1 toque).
- **A5.2** "ciclo de 12 semanas" (12WY) no lugar de trimestre-calendário.
- **B8 decks por DOMÍNIO:** Finanças & Investimentos · Direito · Tecnologia & IA · Pessoas &
  Comunicação · Mundo & Notícias · Vida & Mente (IA sugere o deck por card).
- **Fonte da agenda do dia:** Google Calendar? (pergunta aberta ao Leo).

## Resoluções 6ª rodada (2026-07-09, final)

O Leo aprovou TODAS as pendências da 5ª rodada — agora TRAVADAS. Refletidas no
AETERNUM-WORKFLOWS-V1.md; a tabela de status do topo fica SEM pendências.

**Ex-pendentes, agora TRAVADOS (conforme a recomendação):**
- **A3.1** scorecard: dado cru em **sqlite local** + visão no app/dashboard.
- **A4.2** Rerise **gated pelo scorecard** (≥85% sobe rotina nova).
- **A4.3** graduação de ideias **no app** (1 toque; a IA escreve no vault).
- **A5.2** **ciclo de 12 semanas (12WY)** no lugar de trimestre-calendário.
- **A3.3 punição = PONTOS sobre as Conquistas N1-4** (fazer ganha; furar desconta pouco; scorecard
  <85% + Mentor = a dor principal; **linguagem jamais envergonha**; **stakes reais/anti-charity FORA
  do v1**, só se o kaizen provar necessidade).
- **Decks Anki por domínio TRAVADOS:** Finanças & Investimentos · Direito · Tecnologia & IA · Pessoas
  & Comunicação · Mundo & Notícias · Vida & Mente (template Frente/Meaning/Example/Hook; IA sugere o
  deck por card).

**NOVO — Agenda / Calendários (decisão do Leo):**
- **Fontes:** **Outlook (profissional) = IA SÓ LÊ** · **Google Calendar (pessoal) = IA LÊ E INSERE**
  (insere quando o Leo pede explicitamente ou confirma na captura — lei nº3 estendida a eventos).
- **App ganha superfície de CALENDÁRIO:** visão dia/semana agregando Outlook (read-only) + GCal +
  itens de hora marcada (D18/B6) + ritos (A1/A2/A3). Refletido em F e citado em A1b (resumo da
  agenda), A4 (temas da semana) e D18.
- **Caveat técnico honesto:** Outlook corporativo pode barrar API (registro de app no Graph exige TI;
  a rede tem SSL interceptado) → especificar como **read-only best-effort com fallback** (URL ICS
  publicada ou leitura best-effort). GCal via API/OAuth padrão (lê e insere).
- **Mapa de dados:** calendários = **fonte externa** (Outlook read-only, GCal read/write conforme
  acima); **nada canônico no app**.

**Status:** sem pendências — todas as decisões estão TRAVADAS ou ACEITAS (v1 conceitual fechado).

## Resoluções 7ª rodada (2026-07-09, pós-crítica adversarial)

Crítica adversarial da SPEC por **GPT-5.5 (codex CLI, xhigh, docs inline)**: 15 achados —
**13 aceitos/adaptados, 2 rejeitados parcialmente**. Nenhuma mudança de arquitetura ou de decisão
do Leo; só texto normativo, failure-modes e clarificações. Aplicado na SPEC (§2, §4-§10, §12).

**Aceitos/adaptados (resumo, 1 linha cada):**
1. Lei 3 clarificada: enviar captura = aprovação do **Raw** (verbatim); gate explícito vale para
   qualquer **transformação** da IA (nota estruturada, diário, evento).
2. Degradação da quarentena: A4 pulado → digest oferece **review mínimo de 5 min** (top 5);
   captura de ideias **nunca** é bloqueada (rejeitada a proposta de limitar capturas).
3. **MODO RETORNO** (novo, transversal): ≥7d sem interação → tela "voltar hoje" (3 ações, 5 min),
   digest zerado pra hoje + 3 pendências críticas; Mentor acolhe, não bronca.
4. Privacidade em artefatos: dashboard **publicável** só com métricas não-sensíveis/agregadas;
   saúde/terapia/Edificação/Self Honesty nunca; default privado, publicação opt-in por seção.
5. **MODO MÍNIMO DIÁRIO** declarado: dia válido = A1b 60s + A3 90s (~3 min); pleno ~30-40 min
   (Shutdown substitui a revisão das 19h que o Leo já queria — não é overhead novo).
6. **Semântica de falha do P1** (sem VPS): best-effort com PC ligado; cron perdido dispara no
   próximo wake; Hermes caído → captura enfileira local com retry; digest atrasado aparece na
   próxima abertura; tabela falha→comportamento→o que o VPS resolve.
7. Fila "sessões não compiladas" (B7): compilação falhou → sessão pendente reapresentada até
   compilar ou descartar.
8. Staging com anti-apodrecimento: idade entra na régua do digest + triagem em lote assistida no
   Shutdown (decisão do Leo de triar no ClickUp mantida).
9. Captura ambígua com hora do mesmo dia → "pendente de confirmação" (1 toque); sem resposta até a
   hora, lembrete genérico dispara mesmo assim.
10. Punição harmonizada com a lei 4: desconto leve **só em padrão** (≥3 furos), teto semanal,
    linguagem 100% factual; kaizen monitora correlação com abandono (decisão do Leo mantida).
11. Fila Anki com limite configurável + degradação TSV em 1 toque.
12. Chat: conversa = memória não-canônica; promoção a vault/tarefa só por ação explícita; backup
    do estado Hermes no P2.
13. Calendário operacional: semana ISO · mês civil · ciclo 12WY; no 1º domingo semanal+mensal
    fundem; fechamento de ciclo absorve ambos.
14. Schema terapia: `mode=reflexao, sensitive=true, sensitive_reason=terapia` (nota de
    implementação: atualizar o CLAUDE.md do vault, que hoje lista terapia como modo 10).
15. Manual/SOP: sob demanda, gerado da fonte na lane batch, sem rito de manutenção.

**Rejeitados (com motivo):** bloquear/condicionar novas capturas quando o review atrasa (viola a
lei 2); contagem de "60-100 min/dia de ritos" que somava atividades pré-existentes do Leo (leitura
noturna, treino) como overhead do sistema.

**Status final:** v1 conceitual FECHADO pós-crítica. Próximo gate: review final do Leo → commit.
