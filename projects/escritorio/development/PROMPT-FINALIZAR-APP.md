# PROMPT — Finalizar o Aeternum (app pessoal do Leo)

> Cole daqui para baixo na outra IA. Gerado em 01/set/2026 a partir de auditoria de backlog,
> revisão hostil do app e revisão hostil do BFF. Tudo que está aqui foi verificado no código
> ou no banco; os `file:line` são de `ec8a8d0` (main).

---

## Quem você é e o que vai fazer

Você é engenheiro sênior fechando um app pessoal para UM usuário, o Leo. O produto se chama
**Aeternum** e mora em `projects/escritorio/` (o nome da pasta é antigo). Não confundir com a
fintech `GitHub/Aeternum` (ConsigVerse), que está fora de escopo.

Objetivo do Leo, nas palavras dele: *"quero um app bom para me ajudar"*. A dor nº 1 é
**vazão + disciplina**: capturar → triar → executar → ser cobrado → refletir → planejar.

**Diagnóstico atual, que muda a ordem de tudo:** o código está quase todo escrito. O que não
acontece é USO. No banco de produção (`bff/data.db`, 01/set): `reviews` = 0, `aprendizados` =
0, `objetivos` = 0, obras terminadas = 0, `melhorias` = 1. Cinco features "concluídas" com uso
zero. A causa mais provável: o APK instalado é dev-client sem bundle, o celular só renderiza
com o Metro e o BFF de pé no PC. E os avisos dependem do uptime do desktop: entre 15/ago e
01/set, 5 dias com zero notificação (20, 22, 23, 24, 25/ago).

Portanto: **sua prioridade não é feature nova. É fazer o app abrir sozinho, não mentir, não
travar, e levar o Leo aos ritos que já existem.** Feature nova só na fase 4.

## Stack e como rodar

- **App:** Expo / React Native, Android-first, TypeScript strict, sem react-navigation
  (navegação por ternários em `App.tsx`). Testes: `node --test tests/*.test.mjs` (188 verdes),
  `npx tsc --noEmit` (limpo). Pasta `app/`.
- **BFF:** FastAPI + sqlite (`bff/data.db`), 28 módulos, `main.py` com 87 rotas e 3.253 linhas,
  `store.py` com 3.301. Testes: **`./.venv/Scripts/python.exe -m pytest -q`** de dentro de
  `bff/` (687 verdes, ~51s). O `python` do PATH é o venv do Hermes, não use.
- **Hermes:** agente LLM self-hosted, chamado como subprocess CLI (`hermes.exe -z`, timeout
  150s). Slot único: Mentor, captura, leitura e diário concorrem por ele.
- **Vault** Obsidian no GitHub (`leosbvieira/aeternum`) via PAT; **ClickUp** para tarefas
  (10 listas no Space Personal); **push** via Expo/FCM (funciona; `notif_log` prova).
- Fonte única de horários e tarifas: `bff/ritos.json` → `GET /wiki/parametros` →
  `ParametrosProvider` no app. **Nunca escreva hora ou tarifa à mão** em tela ou script.

### Armadilhas desta máquina (custam horas)

1. **Subir o BFF para teste lê o `.env` real e o worker grava no vault do Leo.** Para E2E use
   `DB_PATH=<temp>/e2e.db` e `VAULT_BRANCH=<branch descartável>`, ou `GITHUB_PAT=""`.
2. O `conftest` do BFF **bloqueia socket real e proíbe `_oneshot`**; quem precisa do Hermes de
   verdade usa `@pytest.mark.hermes_oneshot`. Não contorne.
3. `node --test` só carrega `.ts` que não importa pacote nativo (`expo-*`, `react-native`) nem
   import relativo sem extensão. Padrão do repo: extrair a decisão para módulo puro com `deps`
   injetadas (`filaDrenagem.ts`, `homeAction.ts`, `mesaView.ts`, `closingPoints.ts`).
4. `tests/migracaoPoints.test.mjs` faz grep do literal `POINTS` em todo `src/`, **inclusive
   comentários**. Não escreva essa palavra.
5. Matar o BFF: `taskkill /PID <pid> /T /F`. Processo destacado não sobe pela sessão; o
   Task Scheduler (`start-bff.ps1`, `sync-cron.ps1`) é quem mantém o BFF vivo.
6. `data.db` na raiz de `escritorio/` é lixo antigo. O banco real é `bff/data.db`.
7. Mojibake no terminal Windows quase sempre é artefato de captura, não bug.

## Decisões travadas — NÃO reabrir

- **Punição por pontos fica.** Leo sustentou 2× contra a IA. Calibre: +1/rotina feita, −3 por
  rotina em PADRÃO (≥3 furos na semana ISO), teto semanal. Furo isolado desconta zero. Dia sem
  fechamento não conta furo.
- **Pontos sem ledger.** `pontos.py` é função pura de `routine_checks` + `telemetry`. O placar
  não pode desviar do dado. Nível N1-4 é vitalício (nunca regride).
- **Portão humano** em tudo que a IA produz: nota de leitura (draft → aprovar), cards Anki,
  triagem em lote. A IA propõe, o Leo aprova. Preview da nota é read-only (fidelidade
  byte-a-byte ao ditado).
- **Estante:** frontmatter entra no `/draft`, antes do portão; página = última sessão do
  ciclo; `book_ciclo` copiado na transação; `slug_livro` preserva pontuação.
- **Fatia 2 da estante:** estado `terminando` reserva a obra antes do POST no ClickUp; só
  libera com prova de ausência; sem lease por tempo.
- **Sub-passos de rotina são roteiro**: só o item pai conta no scorecard.
- **App-first**: avisos pelo app; Telegram é ponte. **`closing`** é vocabulário do BFF, não
  renomear.
- **Modo Retorno** (≥7 dias fora → uma porta só, sem pilha de culpa) existe e fica.
- **Melhorias** não viram tarefa, não têm prazo, não cobram atraso.
- Cortados de propósito e continuam cortados: kaizen automático, dashboard no GitHub, lane
  batch claude+codex, AnkiConnect, Garmin, hierarquia 10 anos → dia.

## Método de trabalho

- **Teste antes do conserto**, visto falhar, depois verde. É o padrão do repo e o Leo confere.
- Um commit por defeito ou por fatia, mensagem em português dizendo o sintoma (padrão dos
  commits do repo: "o escaninho dos recusados tinha entrada e nao tinha saida").
- Depois de cada fase, **revisão adversarial dos próprios consertos** com um verificador
  independente por achado. Na última rodada isso pegou 3 regressões graves que o autor não viu
  (compare_digest com str não-ASCII, guarda de atraso ignorando a madrugada, login gerando
  telemetria que o Modo Retorno lia como presença).
- Não afirmar estado que não foi verificado. "Construído" ≠ "validado no aparelho" ≠ "usado".
- Não presumir que número no banco é comportamento real: todo dado até hoje é de teste.
  Mudança de regra de pontos não precisa de migração nem compatibilidade.
- Não mexer no vault pessoal (`Documents\LeonardoLifeMain`) nem em `.env`.

---

## FASE 0 — O app precisa abrir sem o PC (preparar tudo; o build é do Leo)

Você prepara, ele roda `eas build --profile preview`. Entregue:

1. **`expo-updates`** no `package.json` + config em `app.json` (hoje ausente; toda correção
   exige reinstalar APK).
2. **Endereço do BFF em um lugar só**, por perfil do EAS. Hoje está em `app.json`
   (`extra.bffUrl`) E `src/api.ts:12`, ambos `http://192.168.0.2:8000`. A resolução runtime
   (override no SecureStore → extra → constante) fica.
3. **`expo-notifications` com `{ icon, color }`** em `app.json:33` (hoje string nua; o Android
   mascara o alpha e o ícone vira quadrado creme). Canal `default` em
   `src/notifications.ts:118` com `AndroidImportance.DEFAULT` não faz heads-up; os ritos
   precisam de `HIGH`.
4. Escrever o passo a passo de 5 linhas para o Leo: `eas secret:create --scope project --name
   GOOGLE_SERVICES_JSON --type file --value ./google-services.json`, build preview, instalar,
   abrir com o Metro desligado, conferir ícone Æ, splash e ícone da notificação.
5. Apagar ou marcar como fósseis `CHECKLIST-LEO.md` e `RUNBOOK.md` (caminhos
   `C:\Users\LeonardoBalazs\...`, IP `192.168.80.109`, Hermes mock, Expo Go). Substituir por um
   `COMO-RODAR.md` de uma página que reflita o real.

## FASE 1 — Confiabilidade: defeitos verificados, com `file:line`

### BFF (Python)

1. **Crash certo no Anki.** `store.py:3060` faz `SELECT status` e `:3066` lê `row["updated"]`
   → `IndexError` em toda 2ª chamada com run `processing`. Nunca devolve `processing`, nunca
   rouba lease velho. Chega por `main.py:2602` e pelo compile em `main.py:1254`.
   `claim_anki_suggestion` não tem teste.
2. **Duas tarefas ClickUp para uma captura.** `capture_pipeline.py:187-190` busca o marker só
   no Staging. Se o Leo triar antes do retry, o marker sai do Staging e `:207-214` cria um 2º
   card. `tasks.py:855-864` já varre as 10 listas; o pipeline não recebeu o conserto.
3. **Fila travada reportada como zero.** `vault_nao_configurado` devolve o item a `pending`
   sem `bump_attempts` (`capture_pipeline.py:243-247`); `contar_capturas_paradas` só conta
   `attempts > 0` (`store.py:2051`). Vault mal configurado = fila parada e tela dizendo "nada
   parado".
4. **`mark_capture` é read-modify-write sem transação** (`store.py:2093-2143`). Único ponto de
   escrita da fila sem `BEGIN IMMEDIATE` (contraste: `enqueue_capture`, `:1974`). Dois
   escritores levam `attempts` a 5 e o item some das duas filas.
5. **`recover_processing` sem lease** (`store.py:2029-2037`): `UPDATE ... WHERE
   status='processing'` cego, chamado no boot (`main.py:96`). Segundo processo no mesmo db
   desclaima captura em voo → Raw e tarefa duplicados. `init_db` (`:279-288`) e
   `claim_reading_compile` (`:1561`) já filtram por idade; copiar.
6. **Notificação marcada entregue sem prova.** `notify.py:152-160` grava `entregue=1` do ticket
   aceito pela Expo; `conferir_recibos` (`:137-140`) só poda device morto, não reenvia nem
   corrige `notif_log`. `notif_sent_today` filtra `entregue=1` (`store.py:1935-1941`) → digest
   do dia consumido e perdido em silêncio. `fire_due_schedules` repete (`main.py:145-147`).
7. **`/internal/*` sem o endurecimento do login.** `main.py:3183` compara token com `!=`;
   `secrets.compare_digest` só aparece no `/auth/login` (`:1116`). Sem rate limit, backoff ou
   `log_event` de falha (o login tem, `:1080-1131`). Comparar BYTES (lição da rodada anterior).
8. **Encoding do subprocesso Hermes.** `hermes_client.py:209-217` manda `input` em utf-8 mas
   não define `PYTHONUTF8`/`PYTHONIOENCODING` no filho; no Windows o filho lê cp1252.
   `tests/test_sync_cron.py` já mostra `UnicodeDecodeError ... 0xa0` numa thread de leitura.
9. **Timeout do Hermes deixa netos órfãos.** `subprocess.run(timeout=...)` em
   `hermes_client.py:216` mata só o filho; sem `creationflags`/`start_new_session`. Cada
   timeout de 150s deixa processo vivo.
10. **`classify` é o único parse de JSON sem proteção** (`hermes_client.py:288`, `_json.loads`
    cru); os outros `propose_*` tratam.
11. **Herdados da auditoria de agosto, ainda abertos:** A13 — o Mentor "com voz" não existe
    (nenhum gatilho por 3 furos, scorecard <85%, review pulado, pendência >7d; é a promessa de
    aceite da punição). A15 — staleness é código morto (`tasks.py:145`, `update_offset=None`
    sempre → delegação sem data nunca é cobrada). M11 — `pratica_semana` é gravado e nunca
    comparado; a prática da semana nunca expira. M10 — cada captura varre o Staging inteiro com
    `include_closed=True`. A14 — GCal escreve por API e lê por ICS com cache de 15 min; os dois
    caminhos não se falam.

### App (React Native)

1. **Home queima o slot do Hermes em toda abertura.** `Home.tsx:93` chama `getTriagem()`
   dentro do `within()` de 6s (`:69`); `/triagem` leva ~11,6s (comentário em
   `Mesa.tsx:78-83`, onde foi corrigido). Toda montagem e todo foreground: faixa "alguns dados
   não responderam" acesa para sempre, `staging` null, e o `Promise.race` não aborta o fetch,
   que segura o slot único.
2. **Nenhum 401 desloga.** `App.tsx:229` só lê o `exp` local; `sessao.ts:107` devolve `true`
   para token sem `exp`. Único logout é manual (`Settings.tsx:67`). Segredo rotacionado = todas
   as telas em "erro 401" e fila offline parada em `esperar_login` (`offlineError.ts:69`).
3. **65 das 67 chamadas sem timeout.** Só `chatSend` (`api.ts:137`) e `readingApi.ts:103` têm
   `AbortController`. `closingDraft` (`api.ts:550`) passa pelo Hermes; rede caindo sem RST
   deixa `gerando` true para sempre. Solução: um helper único de `fetch` em `api.ts` com
   timeout e formato de erro único (hoje há 3 formatos, e `offlineError.statusDoErro` só
   entende `^erro (\d{3})$`).
4. **Despejo ressuscita depois do dia fechado.** `Fechar.tsx:289` apaga `DUMP_KEY` ao aprovar,
   mas o efeito de desmonte (`:194-200`) regrava `dumpRef.current`. Reabrir Fechar mostra o
   diário já publicado.
5. **Chave do despejo congelada na virada do dia.** `hojeLocal`/`DUMP_KEY` (`Fechar.tsx:153-
   154`) recalculam a cada render, mas os efeitos `:156` e `:194` têm deps `[]`. Texto das
   23h50 vai para a chave de ontem. (Origem: `eslint-disable exhaustive-deps` em `:198`.)
6. **Leitura: caminho novo reconcilia DEPOIS de gravar no vault.** `Capture.tsx:1400-1408`
   compila e depois reconcilia; o caminho de sessão existente faz o certo (`:1335-1346`).
   Buffer não sincronizado → nota incompleta publicada e rascunho que nunca mais fecha
   (`reading_compiled_snapshot_divergente`).
7. **`catch {}` apagando a causa.** `Fechar.tsx:291` diz "nada se perdeu, tenta de novo" tanto
   para 401 quanto para timeout (que pode ter gravado). Também `Fechar.tsx:224`, `:259`,
   `Tasks.tsx:153`, `Triagem.tsx:51`. Usar `offlineError.mensagemDaRecusa` (só a Captura usa).
8. **Erro cru para o usuário.** `Alert.alert(titulo, e?.message)` em `Revisao.tsx:332, 422,
   441, 452, 470, 504`, `Abertura.tsx:311`, `Tasks.tsx:187, 223` → "objetivos: 500" num modal.
9. **`Bearer null`** em `api.ts:78, 168, 196, 210, 236` e `readingApi.ts:82`.
10. **Cleartext global** em `plugins/withCleartextTraffic.js:9`; restringir ao host do BFF até
    o HTTPS.
11. **Teclado Android:** composer do Chat (`Chat.tsx:216`) e entrada da sessão de leitura
    (`Capture.tsx:2327`) sem `KeyboardAvoidingView`; nenhum `windowSoftInputMode`.
12. **Rotinas: os 4 ícones de ação** (`Rotinas.tsx:342-367`, caixa 28×28 + hitSlop 4 = 36dp,
    sem `accessibilityLabel`). O Leo, autor do sistema, não achou o lápis de editar. Alvo ≥44dp
    e rótulo. (O "terminar" da estante já foi consertado; não refazer.)
13. **`sending` global no Chat** (`Chat.tsx:252`) bloqueia os 3 modos enquanto um pensa.

Guardas baratas para o lint textual já existente (`migracaoPoints.test.mjs`): nenhum
`Alert.alert` com `e.message`; toda `fetch` de `api.ts` via helper único; nenhum `within(`
fora de um hook compartilhado; nenhum `Pressable` com `<Feather` como único filho sem
`accessibilityLabel`.

## FASE 2 — Levar o Leo aos ritos (UX que já tem motor)

Estas são frases dele, com o defeito verificado. Aceite observável em cada uma.

1. **B3 — "Ritmos" abre o catálogo, não o hoje.** *"a parte das rotinas nao acho direito.
   Tinha que mostrar a rotina no celular né"*. `Rotinas.tsx` tem zero ocorrências de
   `hoje`/`marcar`/`feito`; Home (`3/6` com barra) e Mesa (`Ritmos · 3 de 6 hoje`) levam ao
   CRUD. Também: a tela se chama `Rotinas` e as 3 portas dizem `RITMOS`. **Aceite:** tocar no
   `3/6` leva a uma tela onde se marca a 4ª rotina e o número sobe ao voltar; um nome só nos
   três lugares. Forma: uma tela, modo "hoje" por padrão, catálogo atrás de "todas / editar".
   Não criar 12º destino na Mesa (quebra o teste de 2160 combinações do `mesaView.ts`).
2. **B1 — Captura sem retorno.** *"aparece coisa 'anotado' embaixo. Mas nao vejo o que, e nao
   sei pra onde vai"*. Três partes: mostrar o que foi capturado e o destino (Staging /
   Edificação / Vault); botão opcional "Estruturar com IA" (ícone `sparkles`) pré-envio; lista
   das capturas recentes na própria aba. Falta `POST /capture/structure` e `GET
   /capture/history` (zero ocorrências hoje). Manter zero-atrito: capturar sem tocar em nada
   continua sendo um toque.
3. **Mentor com voz (A13)** — sem isso a punição é "placar mudo", contra o aceite do item 3 do
   P2. Gatilhos mínimos: 3 furos na semana, review pulado, pendência >7d. O Mentor já recebe
   contexto real das tarefas (`5f8d538`); é acrescentar estes fatos ao prompt e uma linha na
   Home.
4. **M13 — Nível 0 por ~3 meses.** N1 = 700 pontos ≈ 11,5 semanas de aderência 100%, e o `0` é o
   selo da Home. Recalibrar `niveis.limiares` em `ritos.json` (é dado, não código) para o N1 cair
   na 2ª ou 3ª semana. Sem migração: o banco é de teste.
5. **Revisão semanal nunca aconteceu** (`reviews` = 0). Antes de construir mais, rode o rito
   inteiro no aparelho com o Leo e liste o que impede. O nudge de domingo chega; o rito não é
   completado. Mesma pergunta para Edificação (`aprendizados` = 0).
6. **Zerar o banco antes do primeiro uso real** com script que preserve `routines` (5 de
   origem `leo`, inclusive o skincare real gravado por SQL direto) e `books`, e recrie o resto.
   Lembrar que o `SEED` de `routines.py` ainda tem placeholders.

## FASE 3 — Compreensão e descoberta (pedidos repetidos 3×)

1. **Wiki fatia 1B — tela "Como funciona"** (`WIKI-SPEC.md` §12; 1A entregue e mergeada em
   `eae6db2`). *"precisamos de uma página que mostra como funciona o app, o que são diamantes,
   pontos, etc"*. 9 páginas, texto no app com slots, números do BFF via `useParams()`. Porta:
   ARQUIVO da Mesa. Tem que resolver de frente a confusão "duas IAs": Captura é assíncrona e
   fire-and-forget, Mentor é síncrono. Herança da 1A a fechar junto: `Tasks.tsx:25-28` ainda
   copia a lista de áreas à mão (`useParams().areas`); antecedência do review escrita 2×
   (`homeAction.ts` `-180` e `ritos.py` `_MIN_SEMANAL`); `[1,2,3,4]` chumbado em `ui.tsx:468`
   enquanto `niveis.limiares` vem do servidor; `horaCurta` tem 3 implementações.
2. **B5 — Anki como superfície própria.** Hoje vive dentro de Revisão e `POST /anki/sugerir`
   exige `session_id`. `anki_cards.session_id` é NULLABLE (`store.py:196`): soltar a rota e
   adicionar no Chat a ação "vira card?" sobre uma mensagem. Portão humano mantido.
3. **B4 — tag na captura.** Decidir antes: os exemplos dele misturam área (`financeiro`,
   `academia`), projeto (`aeternum`, `zefra`) e contexto (`pessoal`, `trabalho`).
   Recomendação registrada: os dois eixos (área fixa + projeto novo). Encanamento existe:
   `capture_pipeline._create_task` já manda `tags`. Chips opcionais, nenhum selecionado.

## FASE 4 — Infra (você prepara, o Leo provisiona)

**VPS fase 1** (`VPS-PLANO.md`, que vence o `VPS-DEPLOY.md` antigo): tirar o BFF do PC. Mata
os 28% de dias mudos e destrava os gates dos itens 1, 5, 6, 7, 8 e 13 do P2. Não depende do
Hermes: `/internal/nudge` e `/internal/run-digest` não referenciam `hermes_client`. Entregar:
Dockerfile/systemd, Caddy com HTTPS (Android bloqueia cleartext), migração das 6 Scheduled
Tasks para timers a partir do `ritos.json`, `/internal/*` fora da internet, `BACKUP_DIR_2`
para outro volume, e o gate do issue #11743 do Hermes documentado como pré-requisito da fase 2.

## Backlog que fica para depois (não começar sem o Leo pedir)

- **B6 Áreas de Força** (skills por tarefa, estilo Do It Now) e **B7 Foco único recomendado por
  IA a cada hora**: ambos ausentes no código. Toca a economia de pontos.
- **Streak** (`sequencia_atual`/`sequencia_recorde` não existem no BFF) e a **contradição da
  economia**: o BFF tem uma forma de ganhar ponto, o app cita tarifas de tarefa/captura/
  fechamento/shutdown. Streak, tarifas e reconciliação são UMA mudança pensada, não três.
- Fatias 2-4 da wiki (diagramas, teste de render RN, links "o que é isso?").
- Estante fatias 2 e 3: construídas, nunca rodaram em produção (0 obras terminadas). Validar
  no aparelho antes de tocar.

## Código a melhorar (quando estiver dentro do arquivo por outro motivo)

- `Capture.tsx` (2.548 linhas) são 4 telas: captura livre, estante, sessão de leitura,
  preview/aprovação. Cortar por tela. A fila offline já está separada (`captureQueue.ts`,
  `filaDrenagem.ts`).
- `api.ts` (1.217): 67 funções com o mesmo prólogo de 4 linhas → helper único (resolve os
  timeouts e o formato de erro de uma vez).
- `within()`/`run()`/`loadEpoch` copiados byte a byte entre `Home.tsx:61-101` e
  `Mesa.tsx:56-94`; 12 telas repetem `loading`/`refreshing`. Um hook `useCarregar`.
- `Fechar.tsx` é a única tela sem `StyleSheet.create` (559 linhas de estilo inline).
- Três dialetos de erro/loading (`Skeleton`/`ErrorState`, `ActivityIndicator` cru, `Alert`).
- Acessibilidade: 10 de 16 telas com zero `accessibilityLabel`; `colors.faint` sobre `bg` dá
  ~3,4:1 (`theme.ts:34`); 24 `fontSize` entre 9 e 10.5.
- BFF: `main.py` (87 rotas, 3.253 linhas) e `store.py` (3.301) são god-modules; separar por
  domínio quando tocar (captura, leitura, ritos, pontos). Módulos sem arquivo de teste próprio:
  `clickup_client`, `hermes_client`, `ics_client`, `reading_digest`, `resumo_obra`, `tasks`
  (podem estar cobertos indiretamente; confirmar antes de afirmar).
- Suíte do BFF foi de 56s → 200s → 51s; vigiar os testes de compile da estante.

## Só o Leo fecha (liste, não tente)

VPS + domínio; rotacionar `APP_PASSWORD`/`JWT_SECRET`/PAT do vault (expostos em 06/08; ele
decidiu manter o PAT, risco aceito); reconciliar o vault local (8 commits não enviados);
`eas secret` + build preview + instalar; drills no aparelho (1A da wiki, estante 2/3, Mesa,
redesign C2, 5 abas em 360dp, botão físico de voltar); carga financeira D16 (8 cartões, Unimed,
NFs, IR, fim de semana) e recorrência nativa no ClickUp (a API não expõe); credenciais ICS/OAuth
do calendário; decidir `routine_checks` contaminados; plano de 10 anos.

## Formato de entrega

Ao fim de cada fase: (1) lista do que foi feito com commit e teste que prova; (2) o que ficou
de fora e por quê; (3) relatório da revisão adversarial dos próprios consertos, com o que
morreu na verificação; (4) o que só o Leo pode fazer em seguida, em passos de uma linha. Nunca
escreva "concluído" para algo que não abriu no aparelho.
