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
se repetiu: **o que era motor virou código; o que era rito, canal e aprendizado ficou na SPEC.** Os itens 3, 8, 9,
10, 11 e 12 abaixo saíram dessa segunda passada. Agora as 5 rodadas estão rastreadas.

## O P2 (ordenado)

| # | Entrega | Frase do Leo que a originou | Esforço | Por que nessa posição |
|---|---|---|:--:|---|
| 1 | **Carregar as recorrências financeiras reais no ClickUp** e provar o digest cobrando de verdade | *"No d16 1., eu sugiro recriar."* | S | **Não depende de código.** O motor de cobrança existe, roda e foi validado — e a lista Finance está **vazia**. Boletos, cartões, Unimed, condomínio, NFs, 1º checklist de IR. É a entrega mais barata com retorno imediato. |
| 2 | **Punição por pontos + Conquistas N1-4** (A3.3) | *"A3.3. Acho que faz sentido punição. Mas o que seria? Pontuação?"* | M | **Mantida e promovida a 2º por decisão do Leo (12/jul)**, contra a recomendação do GPT-5.6 (cortar) e contra a minha (fazer depois do rito das 5h30). É a 2ª vez que ele sustenta punição contra a IA — ver nota de conflito nº10. **Risco registrado, aceito por ele:** o scorecard hoje mede aderência a rotinas que o sistema ainda não ajuda a executar (não existe o toque das 5h30 nem o check-in das 8h20), então a punição vai descontar ponto num período em que parte do furo é do sistema. Aceite: saldo visível, desconto **só em padrão** (≥3 furos/7d), **teto semanal**, e o Mentor dizendo o motivo — não um placar mudo. |
| 3 | **Notificação pelo app (push in-app) — o canal que ele pediu duas vezes** | *"F. nao é melhor nao ter nada no telegram, apenas APP?"* (2ª rodada, reconfirmado na 3ª) | L | **Órfão estrutural.** Hoje **100% dos avisos saem por Telegram** — digest, fechamento, review, review nudge e até o lembrete de hora marcada (`bff/app/main.py:73`). `bff/app/push.py` e `/internal/notify` **existem e ninguém chama**. Exige dev build + VPS. **É pré-requisito lógico dos itens 4, 5 e 6:** construir o Shutdown das 19h e o toque das 5h30 em cima do Telegram é entregar contra a decisão dele. |
| 4 | **Shutdown das 19h** (rito real, não linha de digest) | *"No a2.1. Shutdown ta bom."* / *"A2.3. Sim, sao 2 ritos diferentes."* | M | O maior buraco no loop diário: hoje o sistema captura e cobra, mas não ajuda a **encerrar o trabalho**. Fecha pendências, mostra `staging: N`, define as 3 prioridades de amanhã. |
| 5 | **A1 mínimo: toque das 5h30 + check-in perguntado às 8h20 + jornal 8h30** | *"5h30: acordar"* / *"A corrida sempre vai ser depois da academia"* / *"No a 1. Sugiro perguntado tb."* / *"8h30 é jornal de leitura de noticias"* | M | O template de dia já existe em código — **na superfície errada** (só no fechamento noturno). Movê-lo para a abertura do dia é reaproveitamento. Garmin fica fora (satélite antes do ritual = dependência invertida). |
| 6 | **Agenda operacional: tarefa própria com hora + resumo matinal + temas da semana** | *"pode ter caso em que eu precise entregar horario x"* / *"de manhã quero um resumo da agenda do dia, com os horários"* / *"é bom colocar também temas que preciso fazer na semana… e ai nos próprios dias tb me lembra"* | M | Compromisso com hora não pode depender do digest das 9h. Completa o scheduler (D18), que hoje só cobre "cobrar terceiro às 15h" — tarefa **própria** com hora não existe. |
| 7 | **Calendário no app: GCal (lê+insere) + Outlook (só lê, best-effort)** | *"a fonte tem que ser Outlook, Google calendário… Google calendário pessoal, ia insere. Outlook é profissional, ia apenas le"* / *"tenho calendário no app tb"* | L | Direção diária depende da agenda. Outlook precisa **degradar com clareza** se a TI bloquear. |
| 8 | **Review semanal + review mensal do 1º domingo + objetivos acumulativos** | *"3. domingo no inicio do mês faz mais sentido"* (3ª rodada) / *"meu objetivo esse ano é rodar rotina de academia. Ai diariamente vou inserindo se fui, e ai no review… eu vejo dashboard disso"* | L | O elo execução→reflexão→planejamento. O **semanal (dom 20h) existe** em cron; o **mensal do 1º domingo, que ele travou, não existe em lugar nenhum** — nem plano, nem cron. **Núcleo dos objetivos:** marcar diariamente, acumular, ver aderência por cadência. **Sem** lane batch, sem Dataview, sem publicação no GitHub. |
| 9 | **Edificação mínima + flag de sensibilidade da terapia** | *"Preciso começar a me edificar e construir"* / *"aprendi Hacks, mas esqueço de aplicar ou refletir"* / *"B9.1. Pode ser subsessão"* | M | Dor explícita e repetida. Versão enxuta: captura reconhecível, 1 aprendizado escolhido no review, vira prática acompanhada. **Junto:** hoje o "sensível" é só uma lista de áreas do ClickUp que neutraliza a linha do Telegram (`config.py:54`) — **não existe** a marca `sensitive=true` na captura/nota que a SPEC promete (lei 7). |
| 10 | **B7 áudio contínuo** (buffer recuperável + hooks falados + 1 compilação) | *"vou manter audio gravando com meus comentários… se eu falar quote é pq quero pegar a citação"* | L | O centro do workflow de leitura, ausente. Aceite: sessão longa, autosave, recuperação após fechar o app, **`quote` preservado verbatim**, uma única compilação. |
| 11 | **Anki: IA sugere candidatos no fim da sessão + card no template** | *"nem tudo de leitura vai pro anki… IA sugere no fim da sessão"* (2ª rodada) / *"no template que tenho no anki. Frente - meaning - example - hook"* | M | **Nenhum dos itens acima gera um card** — nem o item 10, que para na nota do vault. Sem isso, o ★ da tela de leitura continua decorativo. **AnkiConnect (sync automático) fica fora** — primeiro provar que os cards saem certos. |
| 12 | **Agente de triagem em lote do staging** | *"outro agente pode me ajudar a fazer isso"* / *"janelas no dia para migrar"* (2ª rodada) | M | Existe a lista Staging e o contador `staging: N`; **não existe o assistente**. Sem ele, "triagem no ClickUp" é trabalho 100% manual — e staging que acumula é o começo do W27 de novo. |

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
