# Aeternum P2 — backlog derivado da auditoria de fidelidade (12/jul/2026)

> **Origem:** o Leo perguntou "o que eu comentei no dia 9 — a gente implementou? botou no plano?".
> Rastreamos os 4 níveis (doc conceitual → SPEC → plano P0/P1 → código) e submetemos o resultado a um debate
> **Claude Opus 4.8 × GPT-5.6 Sol**, dando ao GPT o `AETERNUM-WORKFLOWS-V1.md` integral e as respostas
> **verbatim** do Leo (5ª/6ª rodadas). Este doc é a síntese. Debate bruto: `.superpowers/sdd/` (ver anexo).

## O diagnóstico

O P0/P1 implementou a **camada operacional** (captura, staging, tarefas, cobrança, filas, sessões) e a validou
E2E em produção. A **camada de ritos, reflexão, planejamento e aprendizado** ficou no SPEC e nunca entrou em
plano nenhum. O SPEC virou o cemitério do feedback: tudo foi absorvido lá, e o plano só puxou o que era motor.

**A causa raiz (achado do GPT, aceito):** o plano P0/P1 foi escrito perguntando *"o que falta no SPEC?"* em vez
de *"cada frase do Leo tem critério de aceite observável?"*. Por isso "existe um template Yoga/Corrida em alguma
tela" foi contado como "o ritual das 5h30 foi implementado" — não foi. Ele existe **como checklist do fechamento
noturno**, na superfície errada e na hora errada.

**Regra para este plano:** cada item nasce de uma **frase verbatim do Leo** e só é dado como feito quando tem
**critério de aceite observável** — superfície certa, horário certo, comportamento exercitado por teste, evidência
vista pelo Leo. Contagem de testes não prova cobertura de escopo.

## Escopo desta auditoria

A 1ª passada cobriu só a **5ª rodada**. Depois auditamos também as rodadas **2ª, 3ª, 4ª e 6ª** (12/jul) — e o padrão
se repetiu: **o que era motor virou código; o que era rito, canal e aprendizado ficou na SPEC.** Dessa segunda passada
saíram os itens **4** (notificação in-app), **9** (review mensal), **10** (flag de terapia), **12** (Anki) e **13**
(triagem em lote), mais o corte explícito da lane batch. Agora as **5 rodadas** estão rastreadas.

O item **2 (rotinas)** não veio das rodadas: é um pedido **novo**, de 12/jul — e expôs que o modelo de rotina do
sistema nunca representou a rotina real do Leo.

## O P2 (ordenado)

| # | Entrega | Frase do Leo que a originou | Esforço | Por que nessa posição |
|---|---|---|:--:|---|
| 1 | **Carregar as recorrências financeiras reais no ClickUp** e provar o digest cobrando de verdade | *"No d16 1., eu sugiro recriar."* / *"acho que faz mais sentido tratar como tarefas diferentes"* (12/jul, sobre os cartões) | S | **Não depende de código.** O motor de cobrança existe, roda e foi validado. **Dados confirmados 12/jul:** Inter mensal dia 5, XP mensal dia 7, Unimed mensal dia 20, NF mensal dia 3 e meta interna do IR anual em 15/mai. **Ainda falta confirmar:** se Inter/XP são todos os cartões ou 2 de 8; se NF é emitir ou pagar; se IR é preparar, enviar ou pagar; regra de vencimento em fim de semana; e ativar/provar a recorrência antes de limpar o lote atual. |
| 2 | **Rotinas como dado editável no app** (bloco do dia + dias da semana + sub-passos ordenados) | *"eu faço skincare e tem uma ordem certa de produtos. tenho que me pesar. tenho que fazer o diário tb. tudo depende da parte do dia e/ou dia da semana (de quarta eu faria máscara, de domingo eu arrumaria a casa)"* (12/jul) | M | **Pedido novo, e é pré-requisito duro do item 3.** Hoje rotina é uma **string numa lista hardcoded** (`bff/app/routines.py`: 6 checks por template, o arquivo se declara *"config, não dado"*). Não existe: **pesagem**, **diário como item**, **ordem de passos** (skincare = 1 caixinha), **condicional por dia da semana** (`weekday` só é usado pra calcular início de semana — conferido), nem **bloco do dia** (todos os checks aparecem juntos na tela das 21h; "acordar-5h30" é marcado retroativamente à noite). **Decisão do Leo (12/jul): editáveis no app** — tela de Rotinas onde ele **adiciona/edita/reordena/remove** sem depender de mim. **Sem isto, a punição (item 3) desconta ponto sobre uma lista de rotinas que não é a dele.** O sistema entra com **poucos exemplos de partida** (abaixo); a lista real é **dado dele**, montada na tela. |
| 3 | **Punição por pontos + Conquistas N1-4** (A3.3) | *"A3.3. Acho que faz sentido punição. Mas o que seria? Pontuação?"* | M | **Mantida e promovida ao topo por decisão do Leo (12/jul)**, contra a recomendação do GPT-5.6 (cortar) e contra a minha (fazer depois dos ritos). É a 2ª vez que ele sustenta punição contra a IA — ver nota de conflito nº10. Ficou atrás do item 2 por **dependência**, não por prioridade. **Risco registrado, aceito por ele:** o scorecard mede aderência a rotinas que o sistema ainda não ajuda a executar (não existe o toque das 5h30 nem o check-in das 8h20), então a punição vai descontar ponto num período em que parte do furo é do sistema. Aceite: saldo visível, desconto **só em padrão** (≥3 furos/7d), **teto semanal**, e o Mentor dizendo o motivo — não um placar mudo. |
| 4 | **Notificação pelo app (push in-app) — o canal que ele pediu três vezes** | *"F. nao é melhor nao ter nada no telegram, apenas APP?"* (2ª rodada, reconfirmado na 3ª) / *"as notificações entram no app sim"* (12/jul, **confirmado**) | L | **Órfão estrutural.** Hoje **100% dos avisos saem por Telegram** — digest, fechamento, review, review nudge e até o lembrete de hora marcada (`bff/app/main.py:73`). `bff/app/push.py` e `/internal/notify` **existem e ninguém chama**. Exige dev build + VPS. **É pré-requisito lógico dos itens 5, 6 e 7:** construir o Shutdown das 19h e o toque das 5h30 em cima do Telegram é entregar contra a decisão dele. |
| 5 | **Shutdown das 19h** (rito real, não linha de digest) | *"No a2.1. Shutdown ta bom."* / *"A2.3. Sim, sao 2 ritos diferentes."* | M | O maior buraco no loop diário: hoje o sistema captura e cobra, mas não ajuda a **encerrar o trabalho**. Fecha pendências, mostra `staging: N`, define as 3 prioridades de amanhã. |
| 6 | **A1 mínimo: toque das 5h30 + check-in perguntado às 8h20 + jornal 8h30** | *"5h30: acordar"* / *"A corrida sempre vai ser depois da academia"* / *"No a 1. Sugiro perguntado tb."* / *"8h30 é jornal de leitura de noticias"* | M | O template de dia já existe em código — **na superfície errada** (só no fechamento noturno). Movê-lo para a abertura do dia é reaproveitamento. Garmin fica fora (satélite antes do ritual = dependência invertida). |
| 7 | **Agenda operacional: tarefa própria com hora + resumo matinal + temas da semana** | *"pode ter caso em que eu precise entregar horario x"* / *"de manhã quero um resumo da agenda do dia, com os horários"* / *"é bom colocar também temas que preciso fazer na semana… e ai nos próprios dias tb me lembra"* | M | Compromisso com hora não pode depender do digest das 9h. Completa o scheduler (D18), que hoje só cobre "cobrar terceiro às 15h" — tarefa **própria** com hora não existe. |
| 8 | **Calendário no app: GCal (lê+insere) + Outlook (só lê, best-effort)** | *"a fonte tem que ser Outlook, Google calendário… Google calendário pessoal, ia insere. Outlook é profissional, ia apenas le"* / *"tenho calendário no app tb"* | L | Direção diária depende da agenda. Outlook precisa **degradar com clareza** se a TI bloquear. |
| 9 | **Review semanal + review mensal do 1º domingo + objetivos acumulativos** | *"3. domingo no inicio do mês faz mais sentido"* (3ª rodada) / *"meu objetivo esse ano é rodar rotina de academia. Ai diariamente vou inserindo se fui, e ai no review… eu vejo dashboard disso"* | L | O elo execução→reflexão→planejamento. O **semanal (dom 20h) existe** em cron; o **mensal do 1º domingo, que ele travou, não existe em lugar nenhum** — nem plano, nem cron. **Núcleo dos objetivos:** marcar diariamente, acumular, ver aderência por cadência. **Sem** lane batch, sem Dataview, sem publicação no GitHub. |
| 10 | **Edificação mínima + flag de sensibilidade da terapia** | *"Preciso começar a me edificar e construir"* / *"aprendi Hacks, mas esqueço de aplicar ou refletir"* / *"B9.1. Pode ser subsessão"* | M | Dor explícita e repetida. Versão enxuta: captura reconhecível, 1 aprendizado escolhido no review, vira prática acompanhada. **Junto:** hoje o "sensível" é só uma lista de áreas do ClickUp que neutraliza a linha do Telegram (`config.py:54`) — **não existe** a marca `sensitive=true` na captura/nota que a SPEC promete (lei 7). |
| 11 | **B7 áudio contínuo** (buffer recuperável + hooks falados + 1 compilação) | *"vou manter audio gravando com meus comentários… se eu falar quote é pq quero pegar a citação"* | L | O centro do workflow de leitura, ausente. Aceite: sessão longa, autosave, recuperação após fechar o app, **`quote` preservado verbatim**, uma única compilação. |
| 12 | **Anki: IA sugere candidatos no fim da sessão + card no template** | *"nem tudo de leitura vai pro anki… IA sugere no fim da sessão"* (2ª rodada) / *"no template que tenho no anki. Frente - meaning - example - hook"* | M | **Nenhum dos itens acima gera um card** — nem o item 11, que para na nota do vault. Sem isso, o ★ da tela de leitura continua decorativo. **AnkiConnect (sync automático) fica fora** — primeiro provar que os cards saem certos. |
| 13 | **Agente de triagem em lote do staging** | *"outro agente pode me ajudar a fazer isso"* / *"janelas no dia para migrar"* (2ª rodada) | M | Existe a lista Staging e o contador `staging: N`; **não existe o assistente**. Sem ele, "triagem no ClickUp" é trabalho 100% manual — e staging que acumula é o começo do W27 de novo. |

## Estado real após a implementação (12/jul/2026, 21h)

> **Regra de status:** `código concluído` significa backend + superfície observável + testes. Não significa que
> credenciais, crons, VPS, dev build ou integrações reais foram ativados. A auditoria contrarian final passou com
> **348 testes BFF**, `tsc --noEmit` + 8 testes do app, `git diff --check` e bundle Android/Hermes (883 módulos).

| # | Estado | Evidência / bloqueio restante |
|---|---|---|
| 1 | **Parcial — externo** | 26 ocorrências Finance já carregadas. Confirmados Inter dia 5, XP dia 7, Unimed dia 20, NF dia 3 e IR até 15/mai. Faltam os verbos de NF/IR, confirmar se existem outros cartões, definir fins de semana e provar a recorrência antes da limpeza do lote. |
| 2 | **Código concluído** | CRUD/reordenação no app, filtros de bloco/dia/template, sub-passos fora do score e testes de troca de template sem pontuação fantasma. |
| 3 | **Código concluído** | Saldo, padrão ≥3/7d, teto, Conquistas N1-4 e painel na Revisão. |
| 4 | **Código concluído; ativação local comprovada** | `eas.projectId`, Firebase, credenciais EAS, instalação Android e smoke de push no aparelho foram comprovados em 12/jul. Falta levar e provar o canal no VPS. |
| 5 | **Código concluído; cron local ativo** | Shutdown 19h com tela, prioridades, follow-ups e staging. Task Windows `Aeternum Shutdown` instalada/Ready; falta levar e provar no VPS. |
| 6 | **Código concluído; crons locais ativos** | Toque 5h30, check-in 8h20, jornal 8h30 e telas. Tasks Windows instaladas/Ready; o jornal abre Capturar. Falta provar no VPS/aparelho. |
| 7 | **Código concluído** | Tarefa própria com hora, scheduler, agenda/temas na Abertura e resumo matinal. Falta smoke com ClickUp real após deploy. |
| 8 | **Código concluído; credenciais pendentes** | ICS GCal/Outlook read-only + inserção GCal pessoal com confirmação, OAuth refresh, idempotência e retry reconciliado. Faltam URLs ICS/OAuth reais e smoke; Outlook continua somente leitura. |
| 9 | **Código concluído** | Review semanal/mensal, janela mensal correta e objetivos acumulativos operáveis na Revisão. |
| 10 | **Código concluído** | Edificação/prática na Revisão+tela, captura `sensivel` inclusive na fila offline, preview neutro e retenção sanitizada. |
| 11 | **Código concluído; soak longo pendente** | STT nativo, abertura offline, recuperação do buffer e hooks falados (`quote`/`citação`) passaram no aparelho. O restore local/remoto e as corridas de navegação têm gates contrarian; falta apenas soak de sessão longa. |
| 12 | **Código concluído; device smoke pendente** | Sugestão após compile, edição/aprovação explícita, export transacional e TSV compartilhável/recompartilhável no app. Falta importação real no Anki. |
| 13 | **Código concluído; integração real pendente** | Propostas em lote, edição e confirmação explícita antes de mover. Falta smoke com Hermes + Staging reais. |

**Não chamar o P2 inteiro de concluído** enquanto os gates dos itens 1, 4, 5, 6, 8, 11, 12 e 13 acima
não tiverem evidência operacional. O código usa carregamento opcional do módulo STT para o app atual não cair antes
do dev build.

## Item 1 — a recorrência é um beco (decisão do D16 forçada pela API)

O MCP do ClickUp **não expõe recorrência** — nem em `create_task`, nem em `update_task` (schemas conferidos em
12/jul). Ou seja: as tarefas financeiras têm data, mas **morrem ao serem concluídas**. Três saídas:

| Saída | Custo | Efeito |
|---|---|---|
| **A. Ligar o "recurring" na UI do ClickUp** | 3 cliques por tarefa (ou o Claude dirigindo o Chrome) | Recorrência **nativa**, que é o que o D16 recomendava |
| **B. Criar as próximas 12 ocorrências** | zero | Funciona hoje e polui a lista (12 tasks por obrigação) |
| **C. O motor do BFF tratar "vence a cada N dias"** | código (S/M) | Independe do ClickUp; era a **decisão em aberto nº1 do D16**, nunca resolvida |

## Item 2 — modelo de rotina (detalhe)

Hoje: `ROUTINES: dict[str, list[str]]` — string numa lista, hardcoded, marcada de uma vez só às 21h.

O que a rotina precisa passar a ter:

| Campo | Para quê |
|---|---|
| `bloco` | manhã / noite — hoje tudo aparece junto no fechamento, e "acordar-5h30" é marcado retroativamente à noite |
| `dias` | todo dia · dias específicos (qua) · só no dia yoga · só no dia corrida |
| `passos[]` | sequência **ordenada** — skincare tem ordem certa de produtos; hoje é 1 caixinha |
| `origem` | `exemplo` (semeado pelo sistema) vs `leo` (criado por ele) — para o sistema nunca sobrescrever o que é dele |

**Sub-passos NÃO contam no scorecard** (decisão do Leo, 12/jul). O passo é **roteiro**: existe pra ele não pular
produto, e é reordenável. Quem entra na conta — e na punição do item 3 — é o **item pai** (`skincare AM` = 1 check
binário). Motivo: 3 produtos virando 3 furos infla o placar e deixa a punição hipersensível a ruído.

**Aceite:** tela de Rotinas no app onde ele adiciona/edita/reordena/remove; o toque da manhã mostra só o bloco da
manhã; o fechamento das 21h mostra só o que era do dia (incluindo a máscara **se for quarta**); o scorecard conta
sobre a lista **dele**, não sobre a semente.

**Exemplos de partida** (só semente — o Leo monta o resto na tela; nada aqui é normativo):

```
manhã · todo dia      acordar 5h30 · pesagem · skincare AM (1. limpeza  2. hidratante  3. protetor)
manhã · dia yoga      yoga · meditação
manhã · dia corrida   academia · corrida (sempre depois da academia)
noite · todo dia      skincare PM (1. limpeza  2. sérum  3. hidratante) · diário · leitura
noite · quarta        máscara
domingo               arrumar a casa
```

## Fora do P2 (cortes explícitos)

> **Punição por pontos: NÃO foi cortada.** O GPT-5.6 recomendou cortar até provar que scorecard + Mentor bastam.
> O Leo decidiu **manter e promover a 2º lugar** (12/jul) — é a segunda vez que ele sustenta essa escolha contra a
> recomendação da IA (a 1ª está na nota de conflito nº10 do doc conceitual). Está no P2 como **item 2**.

| Item | Decisão | Motivo |
|---|---|---|
| Garmin (vibrar no relógio) | Deferido | Construir o satélite antes do rito das 5h30 é inverter a dependência. |
| Dashboard publicável no GitHub | Cortado | Visão simples no app/review primeiro. Publicação só com dados reais e uso real. |
| Kaizen automático (C24) | Cortado | Um agente que otimiza um sistema ainda pouco usado lê **ausência de uso** como erro de configuração. |
| **Lane batch (`claude` + `codex` CLI por OAuth no PC)** | **Cortado — agora explícito** | Pedido da 4ª rodada (*"coisas pesadas… claude + gpt por oauth"*). Estava sendo cortado **implicitamente** dentro do item 8 ("sem lane batch") sem entrada própria. Consequência assumida: dashboard pesado, kaizen e jardinagem do vault ficam sem motor. |
| AnkiConnect (sync automático) + 6 decks | Deferido | O **item 11 entrega o card no template**; a automação de sincronização vem quando houver volume real. |
| Patrimônio mensal automatizado | Deferido | Checklist mensal manual resolve o 1º ciclo. Vem depois do item 1 (carga financeira). |
| Chat por área (E22) / personas | Deferido | Melhora o cockpit, não corrige a vazão. |
| Conselho / Decision Journal | Deferido | Útil, mas episódico. |
| Hierarquia completa 10 anos → dia | Deferido | Provar semana→dia e o ciclo de 12 semanas antes. Markdown simples enquanto isso. |
| Diagramas derivados do vault | Reduzido | Entregar só **tooltips + cheatsheet estático** junto das telas do P2 (isso o Leo pediu duas vezes). |

## Onde o Claude errou (concessões ao GPT)

Registro honesto, porque a matriz original vai ficar no histórico:

1. **Templates de dia ≠ ritual das 5h30.** Eu classifiquei como "implementado parcial". O correto: *modelo de rotina* parcial; *A1a 5h30* **não implementado**; jornal 8h30 não implementado.
2. **Scorecard "feito" é largo demais.** Feito: check binário, persistência, % semanal. **Não** feito: integração com A1, intenção × realizado, objetivo acumulativo, gate ≥85%, alimentação do Mentor.
3. **Detecção de 3 furos não é "metade da punição".** Ela pertence ao motor C10/C11 e seria necessária mesmo sem punição nenhuma. Punição implementada: **zero**.
4. **D18 "implementado" superagrupa.** Tarefa própria com hora, follow-up de terceiro, compromisso de calendário, dedupe digest × lembrete pontual — são coisas diferentes e nem todas existem.
5. **As dúvidas ELI5 não são pedidos.** *"O que é a3.1.? Scorecard? Nao entendi"* não autorizou nada; o que virou código foi **uma recomendação nossa**, aceita depois no *"gostei das suas recomendações"*. A origem correta importa para não inventarmos mandato retroativo.
6. **A minha matriz varreu 10 itens; a 5ª rodada tem ~20 pedidos.** Ficaram de fora do rastreamento: check-in das 8h20, resumo matinal da agenda, jornal 8h30, captura primária pelo app, tarefa própria com hora, temas da semana + lembrete no dia, calendário no app, Outlook read-only, GCal read/write, tooltips (2×), diagramas/SOP no app, Edificação, objetivos acumulativos, buffer local da leitura.

## E onde o SPEC endureceu demais

O risco não foi só perder pedido — foi **cristalizar** o que era inclinação. *"Acho que faz sentido punição. Mas o que seria? Pontuação?"* é uma **pergunta**, e virou no SPEC um subsistema de economia de pontos (desconto leve, teto semanal, Conquistas N1-4). O mesmo com objetivos acumulativos, que viraram uma plataforma de quantified self.

## Já corrigido hoje

- **Hook `quote`** (`app/src/screens/Capture.tsx`): o parser da sessão de leitura só reconhecia `cita*`. Uma citação ditada como *"quote: ..."* — a palavra que o Leo usou — caía silenciosamente como "comentário" e perdia o verbatim. Agora `quote` e `cita*` viram `citação`. Ressalva do GPT, aceita: isso conserta o **texto digitado**; não entrega o pedido, que é **áudio contínuo** (item 8).

## Backlog aberto (pós-P2)

> Itens levantados **depois** do fechamento do P2. Ainda sem critério de aceite fechado nem posição —
> ficam registrados aqui para não virarem órfãos de novo (o erro-raiz que este doc documenta).

| # | Entrega | Frase / origem | Esforço | Notas |
|---|---|---|:--:|---|
| B1 | **Evolução da Captura: Retorno Visível + Botão "Estruturar com IA" (✨) + Histórico em Capturar** | *"1- ao fazer captura, tem que mostrar o que capturou. E um botão para eu "estruturar" com ia, antes de enviar. Posso clicar nele ou nao (podemos colocar aquele simbolo global de ia, acho que é tiipo um diamante, sei la. pesquise.). E tb ter a opção de eu ver o histórico das capturas, hoje nao ta aparecendo em capturar."* (09/ago) / *"aparece coisa 'anotado' embaixo. Mas nao vejo o que, e nao sei pra onde vai"* (16/jul) | M | **Três requisitos integrados na tela Capturar:**<br>**1. Retorno visível:** ao capturar, mostrar o que foi capturado e o destino classificado (Staging, Edificação, Vault), em vez de apenas `"✅ anotado"`.<br>**2. Botão opcional "Estruturar com IA" pré-envio:** botão com o ícone global de IA (diamante / brilho 4 pontas ✨ `sparkles`). O Leo clica se quiser estruturar/limpar o rascunho com a IA antes de enviar.<br>**3. Histórico de capturas em Capturar:** seção/lista com as capturas recentes na própria aba (hoje não aparece).<br>**Falta técnica:** endpoint BFF para estruturação prévia (`POST /capture/structure`) + histórico com verdict (`GET /capture/history`). |
| B2 | **Wiki do sistema dentro do app** — uma tela que explica o Aeternum inteiro pra quem está usando | *"precisamos de uma página que mostra como funciona o app, o que são diamantes, pontos, etc"* / *"sistema inteiro, tipo um wiki"* / *"pode ser pela mesa"* (09/ago) | M | **Terceiro pedido.** Já estava nas decisões travadas da SPEC como "Manual/SOP screen" e no corte "Diagramas derivados do vault → tooltips + cheatsheet estático (**o Leo pediu duas vezes**)" desta mesma tabela. Nunca virou item com critério de aceite — o erro-raiz que este doc documenta, na terceira repetição. **O que forçou agora:** durante o pré-voo de 09/ago o Leo perguntou o que significa "a caminho do N1" e se os diamantes apagados estavam certos, **segurando o próprio app**. Se o autor do sistema não lê a tela, ninguém lê. **Segunda evidência, no mesmo dia e mais grave:** *"as ideias que eu tenho, ou lembranças de tarefas? olhei pro meu quarto e lembrei de comprar cueca, com qual ia eu falo isso?"* — ele não sabe que a **Captura rápida** é exatamente isso. O fluxo existe, funciona e é o principal do sistema; o que falta é a tela dizer. E a pergunta expõe uma confusão específica que a wiki tem que resolver de frente: **há duas IAs com contratos opostos** — Captura é assíncrona e fire-and-forget (você joga fora da cabeça e o worker classifica depois), Mentor é síncrono e conversacional — e nada no app diz qual serve pra quê. Agravado pelo B1: como a captura não mostra o que virou, mesmo acertando a porta ele não teria confirmação. **Porta:** ARQUIVO da Mesa (decisão dele) — atenção, isso muda a contagem de 11 destinos e o teste de 2160 combinações do `mesaView.ts`. **Escopo:** o sistema inteiro, não só a economia. **Fonte:** as seções 1–6 do `AETERNUM-MAPA-DO-SISTEMA.md` são a semente; as 7 e 8 (rotas do BFF,| B3 | **"Ritmos" tem que abrir o hoje, não o catálogo** — os dois botões que mostram progresso do dia levam à tela de gerenciar | *"rotinas, que aparecem todas de todos os dias e pra eu adicionar. Deveria talvez ser em outra tela, não sei"* (09/ago) / *"a parte das rotinas nao acho direito. Tinha que mostrar a rotina no celular né"* (10/ago) | S/M | **A tela não é o defeito; o destino dos botões é.** Conferido: `Rotinas.tsx` **não tem nenhuma noção de "hoje" e não permite marcar nada** — zero ocorrências de `feito`/`marcar`/`hoje` no arquivo. Ela é o CRUD puro (listar, adicionar, editar, reordenar por bloco, apagar), e como catálogo está correta ao mostrar as 12 de todos os blocos e dias. **O furo:** na Home o cartão `RITMOS` mostra `3/6` com barra de progresso (`Home.tsx:203`) e na Mesa o item diz `Ritmos · 3 de 6 hoje` com contador (`mesaView.ts:88`) — **os dois prometem hoje e entregam o catálogo**. Você toca num número que diz 3 de 6 e cai onde não dá pra marcar a quarta. **As rotinas de hoje existem, mas só dentro dos ritos:** bloco da manhã na Abertura, as do dia no Fechar às 21h — e nenhuma das duas é alcançável pelos lugares que exibem o número. **Forma recomendada:** `Rotinas` abre por padrão em "hoje" (rotinas do dia e do bloco corrente, marcáveis ali), com o catálogo completo atrás de um "todas / editar" no topo. Uma tela, dois modos, o padrão sendo o que o número prometeu — evita um 12º destino na Mesa e não mexe no teste de 2160 combinações. **Segundo defeito no mesmo caminho, achado em 09/ago:** *"onde está a tela rotinas?"* — **a porta tem um nome e a sala tem outro.** A tela se titula `Rotinas` (`App.tsx:TITLES.rotinas`), mas **nenhum caminho até ela usa essa palavra**: a Home desenha o cartão `RITMOS` (`Home.tsx:203`) e a Mesa cria o item `"Ritmos"` nos dois grupos (`mesaView.ts:86,90`). Três lugares, duas palavras — o Leo procurou "Rotinas" e não achou. Escolher UMA e usar nos três. **Ficam empilhados no mesmo conserto:** o rótulo não bate com o destino, e o destino não faz o que o número promete. **Terceiro, menor:** as ações de cada linha são quatro ícones Feather de 15px em `textMuted`, sem rótulo — subir, descer, **editar (lápis)** e apagar. O Leo, autor do sistema, não achou o botão de editar. Pouca affordance para uma tela cujo propósito inteiro é editar. **Aceite:** tocar no `3/6` da Home ou da Mesa leva a uma tela onde dá pra marcar a quarta rotina, e o número na origem sobe ao voltar; e o nome do botão é o mesmo nome da tela. |
| B4 | **Escolher tag na captura** — dizer o contexto na hora, em vez de deixar a IA adivinhar | *"para capturas, eu selecionar tag (então, é pessoal, é trabalho? é aeternum? é zefra? é financeiro? é academia?)"* (09/ago) | S/M | **Atenção: os exemplos dele NÃO são as 10 áreas de vida.** `financeiro`→Finance e `academia`→Corpo mapeiam, mas **`aeternum` e `zefra` são PROJETOS** e `pessoal`/`trabalho` é **contexto** — três eixos diferentes numa lista só. Decidir antes de construir: (a) o chip serve pra ele **fixar a área** que hoje o Hermes adivinha e a triagem confirma, ou (b) é uma **dimensão nova de projeto/contexto** que o sistema não tem, ou (c) os dois. **Recomendação: (c).** Fixar a área quando ele já sabe economiza um round-trip do Hermes e mata um item de triagem antes de nascer; e projeto é eixo genuinamente ausente — hoje não existe como separar "Aeternum" de "Zefra" dentro de Trabalho. **Encanamento já existe:** `capture_pipeline._create_task` já manda `tags` pro ClickUp (é assim que `sensivel` e `aguardando` viajam) — a tag nova entra pelo mesmo caminho, sem schema novo. **Cuidado:** chip demais mata o zero-atrito, que é o valor central da captura. Provável forma: uma fileira curta de chips opcionais, nenhum selecionado por padrão, e capturar sem tocar em nenhum continua sendo um toque. |
| B5 | **Anki como superfície própria, alimentada também pelo Mentor** | *"não entendi o anki em revisão, com sugestão de coisa x no card. Tinha que ter tipo uma parte só pro anki... alguém falou uma palavra nova, eu falo com a ia no chat, e digo se quero proposta pra anki"* (09/ago) | M | **Dois problemas separados.** **(1) Descoberta:** os cartões vivem dentro da Revisão, então ele não achou — a Revisão é a tela de *ler a semana*, não de *estudar*. Anki merece destino próprio (ARQUIVO da Mesa, junto do B2). **(2) Fonte única:** hoje o único caminho pra um card é o fim de uma sessão de leitura (`POST /anki/sugerir` exige `session_id`). Ele quer o caminho do dia a dia: ouviu uma palavra nova, conversou com o Mentor, e pede "vira card?". **Achado que barateia isto:** `anki_cards.session_id` é **NULLABLE** (`store.py:196`) — o modelo de dados já aceita cartão sem sessão de leitura. O acoplamento está no **fluxo**, não no schema, então não tem migração. Falta: soltar `session_id` da rota de sugestão e uma ação no Chat que transforme uma mensagem em candidato. **Mantém o portão humano:** a IA propõe, ele edita e aprova um a um, como já é hoje. |
| B6 | **Áreas de Força: Evolução de Skills por Tarefa (Do It Now)** | *"colocar no backlog, áreas de força (entao tipo força, psico, carisma, disciplina, trabalho, etc), em que cada tarefa que eu faço, me da x pontos em algumas skills. E aí eu vou evoluindo cada skill. Bem parecido com o app "do it now""* (10/ago) | M | **Evolução individual por atributo (Força, Psico, Carisma, Disciplina, Trabalho, Lazer):**<br>**1. Associação:** Cada tarefa concluída e/ou rito feito distribui pontos em skills específicas baseadas na área ClickUp ou tags/regras.<br>**2. Persistência:** Tabela local SQLite para registrar XP e nível de cada skill (vitalício, sem regredir).<br>**3. Visualização:** Tela "Ficha de Personagem" ou "Skills" na Mesa exibindo progresso e nível de cada atributo. |
| B7 | **Recomendação Horária da Tarefa Principal (Foco Único) por IA** | *"tarefa principal recomendada pela IA por ordem (essa aí pode se manter e a rerodar a IA a cada 1hr, e aí a IA julga se continua sendo a mais importante)"* (10/ago) | M | **Motor de recomendação recorrente do Hermes (a cada 1 hora):**<br>**1. Avaliação:** O Hermes avalia as tarefas pendentes no ClickUp (vencendo, prioridade, contexto) e sugere a tarefa mais crítica.<br>**2. Reavaliação:** O motor roda em background a cada hora, julgando se mantém o foco atual ou se recomenda uma tarefa nova de maior prioridade.<br>**3. UI:** Card proeminente de "Foco Atual" na Home do app com justificativa de uma linha e botão para concluir. |t que transforme uma mensagem em candidato. **Mantém o portão humano:** a IA propõe, ele edita e aprova um a um, como já é hoje. |
| B6 | **Áreas de Força: Evolução de Skills por Tarefa (Do It Now)** | *"colocar no backlog, áreas de força (entao tipo força, psico, carisma, disciplina, trabalho, etc), em que cada tarefa que eu faço, me da x pontos em algumas skills. E aí eu vou evoluindo cada skill. Bem parecido com o app "do it now""* (10/ago) | M | **Evolução individual por atributo (Força, Psico, Carisma, Disciplina, Trabalho, Lazer):**<br>**1. Associação:** Cada tarefa concluída e/ou rito feito distribui pontos em skills específicas baseadas na área ClickUp ou tags/regras.<br>**2. Persistência:** Tabela local SQLite para registrar XP e nível de cada skill (vitalício, sem regredir).<br>**3. Visualização:** Tela "Ficha de Personagem" ou "Skills" na Mesa exibindo progresso e nível de cada atributo. |

### Detalhamento dos Itens do Backlog Aberto

#### Detalhamento do Item B1 — Evolução da Captura Rápida

> **Origem verbatim:** *"1- ao fazer captura, tem que mostrar o que capturou. E um botão para eu "estruturar" com ia, antes de enviar. Posso clicar nele ou nao (podemos colocar aquele simbolo global de ia, acho que é tiipo um diamante, sei la. pesquise.). E tb ter a opção de eu ver o histórico das capturas, hoje nao ta aparecendo em capturar."* (Leo, 09/ago/2026) + *"aparece coisa 'anotado' embaixo. Mas nao vejo o que, e nao sei pra onde vai"* (16/jul/2026).

##### 1. Retorno Visível do Conteúdo Capturado
- **Comportamento:** após o envio da captura rápida (texto ou voz), a tela exibe o eco do que foi capturado e o destino/verdict atribuído pelo pipeline (ex: `Staging → Tarefa`, `Edificação → Aprendizado`, `Vault → Raw`).
- **UX:** substitui a resposta vaga/cega `"✅ anotado"` por um card/badge de confirmação visível na própria tela de captura, mantendo o fluxo contínuo.

##### 2. Botão "Estruturar com IA" (Pré-envio)
- **Símbolo / Ícone:** Ícone global de IA — diamante / estrela de 4 pontas / brilho ✨ (`sparkles` icon / universal AI badge).
- **Ação:** ao digitar ou ditar um pensamento bruto, o botão permite acionar a IA para refinar, formatar em tópicos, corrigir pontuação/transcrição e extrair a intenção no campo de texto antes de confirmar o envio.
- **Zero Atrito Preservado:** a ação é **opcional** ("Posso clicar nele ou não"). Se não clicar, o envio direto rápido continua intacto.

##### 3. Histórico de Capturas na Tela Capturar
- **Comportamento:** painel/lista de histórico de capturas recentes diretamente na tela `Capturar`.
- **Conteúdo:** exibe as últimas capturas com horário, texto original, texto refinado (se estruturado via IA), status de sincronização (`enviado` / `enfileirado offline`) e a classificação final/destino.
- **Justificativa:** hoje o histórico de capturas não está visível na aba Capturar, impedindo que o Leo consulte o que acabou de enviar ou verifique capturas passadas.

##### Critérios de Aceite Observáveis (B1)
1. **Feedback Imediato:** Ao realizar uma captura, o rodapé/card exibe o texto capturado e o destino classificado (ClickUp Staging / Edificação / Vault).
2. **Estruturação por IA:** Botão com ícone ✨ (`sparkles` / diamante de IA) presente ao lado da caixa de texto de captura. Ao clicar, efetua chamada ao BFF (`POST /capture/structure`) e substitui o texto pelo rascunho estruturado antes do envio.
3. **Histórico Integrado:** Seção/lista de "Histórico de Capturas" visível na tela Capturar com os itens recentes e seus status.

#### Detalhamento do Item B6 — Áreas de Força (Evolução de Skills por Tarefa)

> **Origem verbatim:** *"colocar no backlog, áreas de força (entao tipo força, psico, carisma, disciplina, trabalho, etc), em que cada tarefa que eu faço, me da x pontos em algumas skills. E aí eu vou evoluindo cada skill. Bem parecido com o app "do it now""* (Leo, 10/ago/2026).

##### 1. Definição e Associação de Skills (Atributos)
- **Skills Basilares:** Força, Psico (Intelecto), Carisma, Disciplina, Trabalho, Lazer.
- **Mapeamento de Tarefas:** Cada tarefa concluída no ClickUp gera XP em uma ou mais skills. A distribuição pode ser definida por:
  - **Área/Lista de Destino (Default):**
    - `Corpo` / `Saúde` -> Força
    - `Estudo` / `Leitura` / `Carreira` -> Psico
    - `Relacionamentos` -> Carisma
    - `Trabalho` / `Projetos` -> Trabalho
    - `Lazer` -> Lazer
    - Ritos diários (Abertura, Shutdown, Fechamento no prazo) -> Disciplina
  - **Tags Específicas (Opcional):** Tags na tarefa (ex: `skill:carisma`, `skill:força`) sobrescrevem ou somam pontos específicos.
  - **Classificação automática por IA:** Em tarefas complexas/Staging sem área explícita, a IA do Hermes pode classificar em quais áreas aquela tarefa contribui no momento da conclusão.

##### 2. Persistência de Níveis e Progressão
- **Invariante:** O nível e o XP de cada skill são vitalícios e nunca regridem.
- **Fórmula de Level Up:** Progressão de XP baseada em curvas RPG clássicas (ex: `100 * Nível` XP necessário para passar para o nível seguinte).
- **SQLite:** Criação de tabela local `skills_progress` (`skill_name TEXT UNIQUE, xp INTEGER, nivel INTEGER`).

##### 3. Visualização de Skills no App (UX/UI)
- **Ficha de Personagem:** Nova aba ou seção na Mesa ("Ficha de Personagem" ou "Minhas Skills").
- **UX Visual:** Exibição elegante com barras de progresso circulares ou lineares para cada atributo, com efeitos visuais e o nível de cada skill em destaque.
- **Micro-interações:** Popups e feedback auditivo/visual de "Level Up!" ao completar tarefas cruciais ou fechar ritos que façam uma skill subir de nível.

##### Critérios de Aceite Observáveis (B6)
1. **Atribuição no Backend:** A conclusão de tarefas (`task_completed`) calcula e incrementa a tabela SQLite de skills no BFF.
2. **Endpoint de Skills:** Criação da rota `GET /skills` retornando os níveis e XP atualizados.
3. **Dashboard no App:** Interface "Ficha de Personagem" com progresso em tempo real das 6 áreas de força basilares.

#### Detalhamento do Item B7 — Recomendação Horária da Tarefa Principal por IA (Foco Único)

> **Origem verbatim:** *"tarefa principal recomendada pela IA por ordem (essa aí pode se manter e a rerodar a IA a cada 1hr, e aí a IA julga se continua sendo a mais importante)"* (Leo, 10/ago/2026).

##### 1. Motor de Priorização por IA (Hermes)
- **Background Job:** O BFF agenda um worker rodando a cada 1 hora para ler as tarefas pendentes no ClickUp (especialmente Staging e listas operacionais) e a agenda do dia.
- **Prompt de Julgamento:** A IA (Hermes) avalia a lista completa com base em regras de urgência, contexto, horário do dia e nível de energia para selecionar a **Tarefa Principal (Foco Único)**.
- **Idempotência de Foco:** A cada hora, a IA julga se a tarefa recomendada anteriormente continua sendo a mais importante ou se deve ser substituída. Se a decisão for manter, o ID e estado da tarefa são preservados para evitar alterações bruscas na tela do usuário.

##### 2. Integração no App (Visualização e Ações)
- **Widget de Foco (Home):** Um card proeminente na Home/Mesa exibindo a tarefa recomendada ("Seu Foco Atual: X").
- **Metadados:** Exibe uma justificativa rápida de uma linha escrita pela IA (ex: *"Vence amanhã e impacta a entrega semanal"*).
- **Ações Rápidas:** Botão de check-mark para marcar como concluída diretamente, que aciona o POST de completação e dispara uma nova reavaliação de prioridades pelo motor imediatamente.

##### Critérios de Aceite Observáveis (B7)
1. **Tarefa Recomendada na Rota:** Rota do BFF (`GET /tasks/recommended`) retornando o objeto da tarefa mais importante do momento com a justificativa da IA.
2. **Worker Recorrente:** O sistema atualiza a recomendação em background em intervalos de 1 hora.
3. **Card na Home:** Tela do celular exibe o Foco Atual recomendado, com atualização de estado e sincronização com o ClickUp.

## Mapa do sistema (referência viva)

O documento **`AETERNUM-MAPA-DO-SISTEMA.md`** (nesta mesma pasta) mapeia **todos os fluxos, funcionalidades,
onde o sistema comunica, onde guarda e pra que serve cada peça** — pedido do Leo em 16/jul. Consultá-lo antes de
mexer em qualquer superfície evita repetir a auditoria de fidelidade a cada dúvida de "isso existe? onde vai?".
