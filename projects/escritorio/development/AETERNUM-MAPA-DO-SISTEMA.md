# Aeternum — Mapa do sistema (fluxos, funcionalidades, comunicação e armazenamento)

> **Pedido do Leo (16/jul/2026):** *"uma parte onde eu posso ver todos os fluxos, e funcionalidades do app, e
> onde comunica, e onde guarda, e etc, e pra que serve."*
>
> Este é o **mapa vivo** do Escritório (Aeternum). Não é spec nem plano — é o retrato de **como o sistema
> funciona hoje**, para você (ou uma IA) entender qualquer peça sem reconstruir tudo. Quando o código mudar de
> forma estrutural, atualize aqui. Fonte: leitura direta do código em 16/jul (`app/` + `bff/`),
> revisto em 04/ago para o portão de staging da nota de leitura (§6.2) — ver `READING-STAGING-SPEC.md`.

---

## 1. Visão de 10 segundos

O Escritório é o seu **command center pessoal**: um app de celular (React Native/Expo) que fala com um servidor
próprio (o **BFF**, FastAPI/Python), que por sua vez orquestra **ClickUp** (tarefas), um **vault** de arquivos
markdown (memória bruta), um **modelo de IA** ("Hermes", classificação/redação) e **notificações push**.

```
┌─────────────┐      HTTP/JSON       ┌──────────────────┐
│  APP (Expo) │ ───────────────────► │   BFF (FastAPI)  │
│  celular    │ ◄─────────────────── │   servidor seu   │
└─────────────┘   token Bearer       └────────┬─────────┘
   guarda local                                │
   (SecureStore                    ┌───────────┼───────────┬──────────────┐
    criptografado)                 ▼           ▼           ▼              ▼
                              ┌─────────┐ ┌─────────┐ ┌─────────┐  ┌────────────┐
                              │ ClickUp │ │  Vault  │ │ Hermes  │  │ Push/Tele- │
                              │ tarefas │ │ md files│ │  (IA)   │  │ gram/GCal  │
                              └─────────┘ └─────────┘ └─────────┘  └────────────┘
                              + SQLite local do BFF (estado/fila/histórico)
```

**Regra de ouro do design (leis do sistema):**
- **Lei 1 — nada se perde:** toda captura vira Raw verbatim no vault antes de qualquer processamento; filas persistem em disco.
- **Lei 3 — a IA propõe, você decide:** toda tarefa cai em **Staging**; mover para a área final é sempre um ato explícito seu (triagem).
- **Lei 7 — higiene:** conteúdo sensível nunca vaza em log/preview de notificação; a marca `sensivel` viaja com o dado.

---

## 2. As três camadas (onde cada coisa mora)

| Camada | Tecnologia | Onde roda | Papel |
|---|---|---|---|
| **App** | React Native + Expo (TypeScript) | Seu celular | Todas as telas, captura, STT (voz→texto), fila offline. `app/src/` |
| **BFF** ("Backend for Frontend") | FastAPI + Python | Seu servidor (hoje local/VPS) | Toda a lógica: classifica, cria tarefa, agenda, gera digest, guarda estado. `bff/app/` |
| **Serviços externos** | ClickUp, Hermes(IA), vault, GCal/Outlook, Expo Push, Telegram | Nuvem / disco | Executores: onde tarefa/nota/lembrete de fato existem |

---

## 3. Onde o sistema GUARDA (armazenamento)

| Onde | O quê | Detalhe |
|---|---|---|
| **SecureStore no celular** (criptografado) | Token de sessão, URL do BFF, **fila de captura offline**, **rascunho da sessão de leitura** | `app/src/storage.ts`, `api.ts` (`session_token`, `bff_url`), `captureQueue.ts` (`oq_*`), `readingDraft.ts`. Fila fatiada em chunks de 600 chars (limite de bytes do SecureStore). |
| **SQLite no BFF** (`store.py`) | Estado operacional e histórico | Tabelas: `devices` (push), `routines`+`routine_checks` (rotinas e marcações), `reduction_habits`+`reduction_occurrences` (hábitos a reduzir), `sessions`+`reading_sessions`+`reading_buffer` (leitura), `capture_queue` (fila do servidor), `scheduler` (lembretes), `dia`+`shutdown` (ritos), `temas`, `objetivos`+`objetivo_marcas`, `aprendizados` (edificação), `anki_cards`+`anki_suggestion_runs`, `telemetry`+`notif_log`+`digest_runs`+`ics_cache`. |
| **Vault** (arquivos markdown) | **Raw verbatim** de cada captura + **notas compiladas** da leitura | `vault_client.py`. É a memória permanente. O Raw é escrito ANTES de classificar — se tudo falhar, o texto está salvo. |
| **ClickUp** | Tarefas, cobranças (a lista **Staging** + as áreas) | `clickup_client.py`. É o "sistema de tarefas" de verdade; o BFF só lê/cria/move. |

**Resumo:** o celular guarda o que precisa funcionar offline; o BFF guarda estado/histórico; o vault é a memória
bruta imutável; o ClickUp é onde tarefa vira tarefa.

---

## 4. Onde o sistema COMUNICA (integrações de saída)

| Canal | Direção | Para quê | Arquivo |
|---|---|---|---|
| **Hermes (IA)** | BFF → IA | Classificar captura (tipo/título/quando), redigir rascunho de fechamento, sugerir cards Anki | `hermes_client.py` |
| **ClickUp** | BFF ↔ ClickUp | Criar tarefa em Staging, mover para área, completar, ler abertos p/ digest | `clickup_client.py` |
| **Expo Push** | BFF → celular | Notificação in-app (toque 5h30, check-in, shutdown, digest, review, hora marcada) | `push.py`, `notify.py` |
| **Telegram** | BFF → Telegram | Canal legado de avisos (sendo substituído pelo push in-app — item 4 do P2) | `telegram.py` |
| **Google Calendar** | BFF ↔ GCal | Ler eventos (pessoal) + **inserir** com confirmação | `google_calendar.py` |
| **Outlook / ICS** | Outlook → BFF | Ler agenda profissional (**somente leitura**, best-effort, degrada com clareza) | `ics_client.py`, `agenda.py` |

---

## 5. As telas do app (funcionalidades)

**Tabbar (4 fixas):** `Hoje` · `Capturar` · `Tarefas` · `Mentor`.
As demais entram pela Home e voltam pelo chevron. (`App.tsx`)

| Tela | Arquivo | Pra que serve |
|---|---|---|
| **Hoje / Home** | `Home.tsx` | Cockpit: atalhos para todos os ritos e telas, estado do dia |
| **Capturar** | `Capture.tsx` | Dois modos: **Captura rápida** (tira da cabeça, zero atrito) e **Leitura** (sessão com voz/hooks → nota + Anki) |
| **Tarefas** | `Tasks.tsx` | Lista de tarefas por área (do ClickUp), completar, ver detalhe |
| **Mentor (Chat)** | `Chat.tsx` | Conversa síncrona com o Hermes (modos Mentor/Conselho/Capturas) |
| **Abertura** | `Abertura.tsx` | Rito da manhã: template do dia (yoga/corrida), rotinas da manhã, check-in, resumo da agenda, prioridades de ontem |
| **Shutdown** | `Shutdown.tsx` | Rito das 19h: encerrar o trabalho, fechar pendências, definir as 3 prioridades de amanhã |
| **Fechar o dia** | `Fechar.tsx` | Fechamento noturno 21h: diário + checagem das rotinas do dia → grava daily no vault |
| **Rotinas** | `Rotinas.tsx` | CRUD das rotinas editáveis (bloco/dias/passos ordenados) |
| **Revisão** | `Revisao.tsx` | Review semanal/mensal, scorecard, objetivos, pontos/conquistas, edificação |
| **Edificação** | `Edificacao.tsx` | Aprendizados capturados → escolher 1 para praticar → acompanhar |
| **Triagem** | `Triagem.tsx` | Distribuir itens do Staging para as áreas em lote (a IA propõe, você confirma) |
| **Hábitos a reduzir** | `Habitos.tsx` | Registrar ocorrências de hábitos a reduzir; penalidade nos pontos |
| **Ajustes** | `Settings.tsx` | URL do BFF, login/logout, push |

---

## 6. Os fluxos principais (passo a passo)

### 6.1 Captura rápida  ⚡ *(o que gerou este documento)*

```
Você escreve/dita  →  [Enviar]  →  POST /capture
                                      │
                        BFF enfileira e responde "✅ anotado"  ◄── o recibo que você vê
                                      │  (fire-and-forget: NÃO processa na hora)
                                      ▼
                        worker de fundo (capture_pipeline.py), a cada N segundos:
                         1. escreve Raw verbatim no vault           (nada se perde)
                         2. Hermes classifica → tipo/título/quando
                         3. se tarefa/cobrança → cria card em STAGING (ClickUp)
                            se `hack:`/`aprendizado:`/`insight:`   → vira Edificação (não é tarefa)
                            se só nota                              → fica no vault
                         4. se tem hora marcada → agenda lembrete (scheduler)
                                      ▼
                        materializa em:  ClickUp/Staging  ·  Vault (Raw)  ·  Edificação
                                      ▼
                        você distribui depois pela TRIAGEM (Staging → área)
```

- **"✅ anotado" = recibo, não resultado.** Significa "recebi e guardei, processo em fundo". `main.py:863`.
- **Prefixos especiais:** `sensível:` marca a captura (preview neutro, lei 7); `hack:`/`aprendizado:`/`insight:` viram edificação, nunca tarefa.
- **Offline:** se não há rede, a captura fica na fila do celular (badge "N capturas seguras no aparelho") e reenvia sozinha. `captureQueue.ts`.
- **Buraco atual (backlog B1):** a tela não mostra o que a captura virou nem pra onde foi. É intencional (zero-atrito), mas está no backlog dar um retorno visível.

### 6.2 Sessão de leitura  📖

```
Modo Leitura → informa livro/página → [Começar] (com ou sem microfone)
  durante a leitura: fala/escreve trechos, prefixando "citação/comentário/ideia/lista"
  cada registro → buffer local (recuperável se fechar o app) + autosave no servidor
[Compilar] → BFF junta o buffer → Hermes → PREVIEW da nota (read-only; NADA no vault ainda)
   ├─ [Salvar no vault] → NOTA limpa no vault + candidatos ANKI para revisar
   └─ [Rejeitar]        → volta às notas cruas para corrigir e compilar de novo
```
- Buffer nunca some: salvo no celular (`readingDraft.ts`) e no servidor (`reading_sessions`/`reading_buffer`). Recupera após fechar o app, reconcilia local×remoto.
- **Portão humano (lei 3): compilar NÃO publica.** A nota só entra no vault quando você aprova o preview — o mesmo princípio que os candidatos Anki já seguiam. O preview é read-only de propósito: você aprova ou rejeita, nunca edita o texto, então o que vai pro vault continua derivado byte-a-byte do que você ditou.
- Estado "staged" = `pending` + `draft_md` preenchido (sem status novo no banco). Enquanto há preview o buffer fica **congelado** dos dois lados — o servidor recusa edição com `reading_draft_ja_gerado` — para o `source_digest` não divergir entre gerar e aprovar.
- Só limpa o buffer **depois** que o vault confirma a nota (não perde nada num crash). Se o vault falhar, a sessão **continua staged** e o retry reusa o rascunho já salvo, sem gastar outra chamada do Hermes.

### 6.3 Tarefas e cobrança

```
Tarefas vêm do ClickUp (por área) → digest diário (9h) seleciona o que cobrar por cadência
Staging é excluído do digest de cobrança; envelhecimento do Staging vira alerta próprio
Cobrança de terceiro → lembrete agendado (scheduler) "cobrar às 15h"
```

### 6.4 Ritos do dia (loop diário)

```
5h30  Abertura   → template do dia, rotinas da manhã, check-in 8h20, jornal 8h30
19h   Shutdown   → encerra trabalho, 3 prioridades de amanhã
21h   Fechar     → diário + rotinas do dia (só as que valem hoje) → daily no vault
dom   Review     → semanal (20h) + mensal (1º domingo) → scorecard, objetivos, pontos
```
Cada rito é disparado por **notificação push** (ou cron no servidor) e abre a tela certa. `App.tsx:tabDaNotificacao`.

### 6.5 Pontos, objetivos e hábitos

- **Pontos/Conquistas N1-4** (`pontos.py`): fazer ganha ponto; furar desconta **pouco e só quando vira padrão** (≥3 furos/7d), com teto semanal. Nível é vitalício (deriva do pico, não regride).
- **Objetivos acumulativos:** marcar diariamente, acumular, ver aderência por cadência no review.
- **Hábitos a reduzir:** registrar ocorrência → penalidade nos pontos; dá pra desfazer.

---

## 7. Rotas do BFF (contrato completo, por área)

> Todas exigem `Authorization: Bearer <token>` exceto `/health` e `/auth/login`. Fonte: `main.py`.

| Área | Rotas |
|---|---|
| **Infra/auth** | `GET /health` · `POST /auth/login` |
| **Captura** | `POST /capture` (fire-and-forget) · `POST /captures/retry-failed` |
| **Sessões / Leitura** | `POST /sessions` · `POST /reading/sessions` · `POST/PATCH/DELETE /reading/sessions/{id}/buffer[/{seq}]` · `GET /reading/sessions/pending` · `GET /reading/sessions/{id}` · `POST .../reconcile` · `POST .../draft` (gera o preview) · `POST .../compile` (aprova → vault) · `DELETE .../draft` (rejeita) · `POST .../discard` |
| **Chat / Push** | `POST /chat` · `POST/DELETE /devices` |
| **Tarefas** | `GET /tasks` · `POST /tasks` · `POST /tasks/{id}/complete` · `GET /tasks/{id}` · `GET /digest` |
| **Pontos/Review** | `GET /pontos` · `GET /review/weekly` · `GET /review/monthly` |
| **Hábitos a reduzir** | `GET /habitos-reduzir[/historico|/{id}]` · `POST /habitos-reduzir` · `PATCH/DELETE /habitos-reduzir/{id}` · `POST .../{id}/ocorrencias` · `POST .../ocorrencias/{id}/undo` |
| **Rotinas** | `GET/POST /routines` · `PATCH/DELETE /routines/{id}` · `POST /routines/reorder` · `POST /routines/check` |
| **Abertura/Shutdown** | `POST /dia/template` · `GET /abertura` · `POST /abertura/checkin` · `GET/POST /shutdown` |
| **Fechamento noturno** | `GET /closing/routines` · `POST /closing/draft` · `POST /closing/approve` |
| **Anki** | `POST /anki/sugerir` · `GET /anki/cards` · `PATCH /anki/cards/{id}` · `POST /anki/export` |
| **Triagem** | `GET /triagem` · `POST /triagem/aplicar` |
| **Edificação** | `GET/POST /aprendizados` · `POST /aprendizados/{id}/praticar` · `POST /aprendizados/{id}/status` |
| **Objetivos** | `GET/POST /objetivos` · `PATCH/DELETE /objetivos/{id}` · `POST /objetivos/{id}/marcar|/desmarcar` |
| **Agenda/Temas** | `GET /agenda` · `POST /agenda/google-calendar` · `GET/POST /temas` · `DELETE /temas/{id}` |
| **Internos (cron/worker)** | `POST /internal/nudge` · `POST /internal/notify` · `POST /internal/run-digest` |

---

## 8. Módulos do BFF (o que cada arquivo faz)

| Arquivo | Papel |
|---|---|
| `main.py` | Rotas HTTP + workers de fundo (fila de captura, disparo de schedules) |
| `capture_pipeline.py` | O coração da captura: Raw → classificação → Staging (idempotente, retomável) |
| `store.py` | SQLite: schema e todo acesso a dados |
| `clickup_client.py` | Integração ClickUp (áreas, Staging, criar/mover/completar) |
| `hermes_client.py` | Chamadas ao modelo de IA (classificar, redigir, sugerir) |
| `vault_client.py` | Escrita no vault (Raw verbatim + notas compiladas) |
| `tasks.py` | Lógica de tarefas, digest, triagem em lote |
| `cadence.py` | Regras de cadência (o que cobrar quando) |
| `pontos.py` / `objetivos.py` | Economia de pontos/conquistas e objetivos acumulativos |
| `routines.py` | Sementes/utilidades de rotina |
| `agenda.py` / `google_calendar.py` / `ics_client.py` | Agenda: GCal (lê+insere), Outlook/ICS (só lê) |
| `push.py` / `notify.py` / `telegram.py` | Canais de notificação |
| `anki.py` / `reading_digest.py` | Cards Anki e compilação da leitura |
| `auth.py` / `config.py` | Token e configuração/segredos |

---

## 9. Estado atual (leia junto com o P2-BACKLOG)

O **P2 está com código concluído** (13 itens), mas vários dependem de **ativação operacional** (VPS, credenciais,
crons, dev build). Ver `AETERNUM-P2-BACKLOG.md` seção "Estado real". Buracos conhecidos que afetam o dia a dia:

- **Retorno da captura** (backlog B1): você não vê o que a captura virou.
- **Push in-app vs Telegram** (item 4): ainda saindo por Telegram até provar o canal no VPS.
- **Recorrência financeira** (item 1): tarefas financeiras "morrem" ao completar (ClickUp não expõe recorrência via API).

---

*Atualize este mapa quando um fluxo, tela, rota ou integração mudar de forma estrutural. Ele existe para você
nunca mais precisar reconstruir o entendimento do sistema do zero.*
