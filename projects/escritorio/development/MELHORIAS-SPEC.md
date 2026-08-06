---
artifact: skill-spec
capability: escritorio
skill: melhorias (fila sem prazo)
status: implemented
date: 2026-08-06
source_refs:
  - AETERNUM-SPEC.md
  - AETERNUM-AUDITORIA-2026-08.md
  - CAPTURE-GRAMMAR-SPEC.md
  - "conversa 2026-08-06 (Leo + Claude): onde registrar melhorias"
engine: nenhum (hook textual determinístico, sem inferência)
implements: "fila de melhorias por alvo — app / empresa / fluxo — que nunca vira tarefa"
---

# SKILL SPEC — melhorias

Fila para registrar **melhorias**: do próprio Aeternum, dos sistemas da empresa e de
fluxos/processos. Não tem prazo, não vira tarefa, não entra no ClickUp e **nunca cobra
atraso**.

## O buraco que fecha

O Leo perguntou onde registrar melhoria. Não havia lugar — havia três lugares errados:

1. **Classificador sem o conceito.** `hermes_client.CLASSIFY_FRAME` só conhece
   `nota | tarefa_pessoal | tarefa_trabalho | cobranca`. "melhorar o filtro de tarefas"
   não é nenhum deles.
2. **Se caísse em `nota`, sumia.** `capture_pipeline` só cria card quando
   `tipo != "nota"`. O texto virava um arquivo em `00-Raw/` e **nenhuma tela voltava a
   mostrá-lo**. Escreve-e-esquece.
3. **Se virasse tarefa, morria no cemitério.** As 9 áreas da triagem são áreas de
   **vida** (Trabalho, Corpo, Saúde Mental, Responsabilidade, Finance, Carreira, Estudo,
   Relacionamentos, Lazer) — nenhuma é "o sistema". E sem prazo, `bucket()` em
   `Tasks.tsx` classifica `days_overdue === null` como `backlog`, onde nada cobra e nada
   lembra.

## A tese

**Melhoria não tem prazo, tem momento.** Melhoria do app só é acionável quando o Leo está
programando comigo; melhoria de empresa/fluxo só quando ele para pra pensar em sistema — e
disso já existe rito, o review semanal. Forçar qualquer uma na lista de tarefas produz ou
**culpa** (atraso inventado) ou **lixo** (backlog): é a mesma inversão de incentivo que a
auditoria de 2026-08 encontrou nos ritos.

## Decisões

- **D-A — alvo, não área.** `app` | `empresa` | `fluxo`, e `NULL` = a triar. O alvo é
  opcional na captura porque decidir na hora é atrito; a fila pergunta depois, num toque.
- **D-B — `app` fica fora da cobrança.** O review conta `paradas` = `novo` com alvo
  `NULL`/`empresa`/`fluxo`. As de `app` aparecem numa linha informativa separada. Contá-las
  no "escolhe 1" transformaria a fila numa dívida crescente, e ele registra melhoria de app
  o tempo todo.
- **D-C — uma escolhida por vez.** Duas escolhas simultâneas valem tanto quanto nenhuma.
  Espelha `definir_pratica` da Edificação.
- **D-D — sem write extra no vault.** O Raw verbatim da captura já cumpre a lei 1
  (`write_raw` roda **antes** dos hooks). As melhorias de alvo `app` são lidas por mim via
  `GET /melhorias?alvo=app` — mesma durabilidade que aprendizados, pontos e rotinas.
- **D-E — a semana vem do servidor.** `escolher` não aceita semana do cliente: relógio de
  celular errado gravaria a semana errada e o review perderia o vencimento.

## Ciclo de vida

```
CAPTURA  "melhoria: …" | "melhoria app: …" | "ideia empresa: …"
   │  (hook determinístico, ANTES do Hermes — não paga inferência)
   ▼
novo ──────────────► escolhida ──► feita
  │   escolher(semana)     │        ▲
  │                        └────────┘
  └────────────────────────────────► descartada
                                        │
                              (status novo devolve à fila)
```

`alvo` é ortogonal ao status e pode mudar a qualquer momento pela triagem.

## Hook de captura

| Prefixo | Resultado |
|---|---|
| `melhoria:` / `ideia:` | melhoria com alvo `NULL` (a triar) |
| `melhoria app:` / `ideia app:` | alvo `app` |
| `melhoria empresa:` | alvo `empresa` |
| `melhoria fluxo:` | alvo `fluxo` |
| `sensivel: melhoria …` | os dois hooks compõem; a marca sensível viaja junto |

Só os três alvos conhecidos casam. `melhoria xyz:` **não** é hook — cai na captura normal
(Raw + Staging + triagem), porque engolir criaria uma melhoria cujo texto começaria com
`xyz:`, ruído que ninguém veria. O prefixo é ancorado no início: "pensei numa melhoria: x"
é captura comum.

## API

| Método | Rota | O que faz |
|---|---|---|
| GET | `/melhorias?alvo=&status=` | lista a fila; filtros validados na borda (422) |
| POST | `/melhorias` | cria manualmente (`texto`, `alvo?`, `sensivel?`) |
| POST | `/melhorias/{id}/alvo` | triagem: define `app`/`empresa`/`fluxo` |
| POST | `/melhorias/{id}/escolher` | marca a da semana; 404 se já `feita`/`descartada` |
| POST | `/melhorias/{id}/status` | `novo` / `feita` / `descartada` (`escolhida` é 422) |

`GET /review/weekly` ganhou o bloco:

```json
"melhorias": { "paradas": 1, "escolhida": {…}|null, "app": 5 }
```

E `weekly_review_text()` ganhou duas linhas com pesos diferentes — `paradas` pede decisão,
`app` é informação:

```
melhorias: 1 melhoria parada — escolher 1 no review
melhorias de app: 5 pro Claude
```

## Superfícies no app

- **Melhorias** (`Melhorias.tsx`, na Home → Ferramentas): campo de entrada com chips de
  alvo, "desta semana" no topo, "a triar · um toque", fila por alvo, resolvidas colapsadas.
- **Revisão**: linha da escolhida ou "N melhorias paradas — escolher 1", + linha
  informativa das de app. Toque abre a tela.
- **Capturar**: bloco "COMEÇANDO COM" listando os prefixos. Os hooks existiam desde o P2
  item 10 e **nunca apareceram em tela nenhuma** — atalho invisível é atalho não usado.

## Aceite

- [x] `melhoria:` não chama o Hermes e não cria task no ClickUp
- [x] alvo inline (`melhoria app:`) e alvo omitido (`melhoria:` → a triar)
- [x] `sensivel:` compõe com o hook e a marca chega ao registro
- [x] retry da fila não duplica (UNIQUE em `origem_captura_id`)
- [x] prefixo no meio da frase e alvo desconhecido **não** disparam o hook
- [x] uma escolhida por vez; `feita`/`descartada` não podem ser reabertas por `escolher`
- [x] `paradas` no review ignora as de alvo `app`
- [x] alvo desconhecido vindo de um BFF mais novo cai na triagem em vez de sumir
- [x] E2E real: `/capture` → fila → hook → `GET /melhorias` → `/review/weekly`, com
      `/tasks` intacto

**Testes:** `bff/tests/test_melhorias.py` (32) · `app/tests/melhoriasView.test.mjs` (7).
