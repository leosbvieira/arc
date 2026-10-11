---
artifact: archive-local-branch-2026-09
capability: escritorio
status: closed
scope: o que era o ramo local do PC (U00–U06 mock-first) e o que dele entrou na linha da nuvem
authored: 2026-09-12
---

# Arquivo — ramo `local-2026-09`

**Onde está:** branch `local-2026-09` (33591d5) e tag `local-snapshot` (543f874), ambas
locais neste clone; backup fora do repo em `Arc/backup-local-2026-09-11/` (o `data.db`
do BFF local, `digesttest.db` e `development-execution.tgz`). Nada disso foi enviado ao
origin. O ramo é só leitura daqui pra frente: a linha principal é `main` (origin), e a
linha local **não** volta a ser desenvolvida.

## O que era

Um segundo escritório, escrito no PC entre agosto e setembro de 2026 a partir da base
1df6d1b, enquanto a nuvem seguia da mesma base por 178 commits. Os dois divergiram por
completo: nenhum arquivo ficou idêntico. O local era **mock-first** — tudo passava por
contratos de operação (`operation_contract.py`, `operation_ledger.py`, `recovery_scope.py`,
`delivery_ledger.py`) com estados formais, journal no app (`recovery-native`) e suites
U02–U06 em Jest sobre um store próprio (`workspace-context`). Hermes era um servidor HTTP
atrás de uma bridge; ClickUp, vault e Telegram ficavam atrás de gates de capability que
nunca foram abertos. Tema claro.

A nuvem é o app **real**: Hermes por CLI oneshot, ClickUp por REST, vault no GitHub, push
Expo com Telegram de ponte, tema escuro ("midnight desk"), 700+ testes de BFF e 200+
módulos puros do app em `node --test`.

## Decisão (11/09/2026, Claude x Codex, confirmada pelo Leo)

Nuvem é a principal. Do local, entra só o que é **segurança, infraestrutura ou
durabilidade** e cabe na arquitetura da nuvem sem trazer a arquitetura do local junto.
Tudo o mais (contratos de operação, ledgers, recovery journal, bridge do Hermes, gates de
capability, tema claro, suites U0x) fica aqui, arquivado.

## O que entrou (branch `escritorio/port-local-2026-09`, sobre origin/main 9f1fdd2)

| Commit | Item |
| --- | --- |
| 3d14a82 | BFF: token interno comparado em tempo constante; JWT exige `exp/iat/sub` e `sub=owner`; 422 genérico sem eco; segredos vazios recusam o boot |
| dff8095 | CI com `permissions: contents: read` e actions por SHA; hooks do Codex portáveis; D-15 (BFF calcula cadência; push-first + Telegram) |
| fb4fcec | App: URL do BFF validada em runtime e no build; http só em dev; cleartext só quando permitido; toque mínimo 44 e labels de acessibilidade |
| b6b7dfa | Captura gravada na fila ANTES do primeiro POST; BFF responde 409 quando a mesma `client_key` chega com outro conteúdo |
| 9d75374 | Push reconciliado no boot (rotação, permissão revogada); "Sair" com prazo e sem diálogo de permissão |
| 742faa9 | Limites de tamanho por campo (não middleware global); reserva atômica do slot do dia pro digest e nudges, com `incerto` |
| b304f0f | Locks com hashes (uv); CI instala do lock; `ops/` candidatos pro VPS (unit, env, release/backup/rollback) |
| ea94841 | Jest + Testing Library pra cenários de tela ao lado do `node --test`; resposta tardia não apaga o que foi digitado |

## O que ficou de fora, e por quê

- **Contratos/ledgers de operação e recovery journal**: resolvem um problema que a nuvem
  resolve com `client_key` + fila no SecureStore + `capture_queue` no BFF. Trazer os dois
  seria ter duas fontes de verdade.
- **Hermes como servidor/bridge**: a nuvem decidiu CLI oneshot (D-x); a bridge não tem
  onde encaixar.
- **Canal duplo independente (push E Telegram)**: rejeitado em D-15 — push primeiro,
  Telegram só quando o push não entrega.
- **Tema claro e as suites U02–U06**: testam telas e um store que não existem na nuvem.
- **nginx**: a nuvem usa Caddy.

## Se um dia precisar de algo daqui

`git show local-2026-09:projects/escritorio/<caminho>`. As ideias mais reaproveitáveis
que **não** foram portadas: `request_limits.py` (limite por rota com contagem de bytes do
stream, útil se um dia o Caddy não bastar) e `digest_delivery.py` (máquina de estados de
entrega com recibos por canal).
