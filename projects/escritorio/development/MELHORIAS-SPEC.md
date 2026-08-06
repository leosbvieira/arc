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
  celular errado gravaria a semana errada e o review perderia o vencimento. `GET /melhorias`
  devolve a semana ISO corrente junto com a lista, pelo mesmo motivo: a tela precisa saber se
  a escolhida é *desta* semana sem recalcular data no cliente.
- **D-F — a escolha VENCE na virada da semana.** A escolha de outra semana não é "a desta
  semana", mas também não é apagada — apagar seria o sistema decidindo por ele (lei 3). Ela sai
  do lugar de compromisso corrente e vira a pergunta **"fez?"**, exatamente como
  `praticas_sem_avaliacao` faz na edificação.
- **D-G — o convite promete a ação que a tela oferece.** `a_triar` (sem alvo) e `escolhiveis`
  (empresa/fluxo) são contados em separado: o card de "a triar" só tem os chips de alvo, o botão
  *fazer esta semana* mora no card da fila. Um CTA "escolher 1" contando os dois mandaria ele
  procurar um botão que aquela seção não tem.

## Ciclo de vida

```
CAPTURA  "melhoria: …" | "melhoria app: …" | "melhoria empresa: …"
   │  (hook determinístico, ANTES do Hermes — não paga inferência)
   ▼
novo ──────────────► escolhida ──────────► feita
  │   escolher(semana)     │  (semana X)     ▲
  │                        │                 │
  │                        ▼ virou a semana  │
  │                     VENCIDA ─────────────┘
  │                     "fez?" — não some, não vira "desta semana"
  │                        │
  └────────────────────────┴───────────────► descartada
                                                │
                                    (status novo devolve à fila)
```

`alvo` é ortogonal ao status e pode mudar a qualquer momento pela triagem.

## Hook de captura

| Prefixo | Resultado |
|---|---|
| `melhoria:` | melhoria com alvo `NULL` (a triar) |
| `melhoria app:` | alvo `app` |
| `melhoria empresa:` | alvo `empresa` |
| `melhoria fluxo:` | alvo `fluxo` |
| `sensivel: melhoria …` | os dois hooks compõem; a marca sensível viaja junto |

**`ideia:` NÃO é gatilho.** A palavra já é da casa: é um dos modos da gramática de leitura
(`CAPTURE-GRAMMAR-SPEC.md`) e a tela de Captura manda dizer "ideia" durante o ditado.
Sequestrá-la fazia *"ideia: levar a Maria pra jantar sexta"* nunca chegar ao classificador —
sem data parseada, sem card, sem lembrete — com o recibo genérico "✅ anotado" escondendo a
troca de destino.

**Prefixo sem texto não vira registro.** `melhoria:` sozinho (ditado cortado, envio acidental)
cai no caminho normal. A borda HTTP já recusava texto em branco com 422; a fila — que é quem
recebe entrada não controlada — entrava sem guarda e produzia um card vazio impossível de
triar que engrossava o "escolher 1" do review. O hook de aprendizado tinha o mesmo buraco e
foi fechado junto.

Só os três alvos conhecidos casam. `melhoria xyz:` **não** é hook — cai na captura normal
(Raw + Staging + triagem), porque engolir criaria uma melhoria cujo texto começaria com
`xyz:`, ruído que ninguém veria. O prefixo é ancorado no início: "pensei numa melhoria: x"
é captura comum.

## API

| Método | Rota | O que faz |
|---|---|---|
| GET | `/melhorias?alvo=&status=` | lista a fila + a semana ISO corrente; filtros validados na borda (422) |
| POST | `/melhorias` | cria manualmente (`texto`, `alvo?`, `sensivel?`) |
| POST | `/melhorias/{id}/alvo` | triagem: define `app`/`empresa`/`fluxo` |
| POST | `/melhorias/{id}/escolher` | marca a da semana; 404 se já `feita`/`descartada` |
| POST | `/melhorias/{id}/status` | `novo` / `feita` / `descartada` (`escolhida` é 422) |

`GET /review/weekly` ganhou o bloco:

```json
"melhorias": {
  "paradas": 3, "a_triar": 2, "escolhiveis": 1,
  "escolhida": {…}|null,        // SÓ a desta semana
  "vencidas": [{…}],            // escolhas de semanas anteriores em aberto
  "app": 5
}
```

E `weekly_review_text()` ganhou linhas com pesos diferentes — `escolhiveis` pede decisão,
`a_triar` pede um toque, `vencidas` pergunta, `app` é informação:

```
melhorias: 1 melhoria parada — escolher 1 no review
melhorias: 2 melhorias a triar — um toque cada
melhoria escolhida em 2026-W30 segue em aberto
melhorias de app: 5 pro Claude
```

⚠️ **Lei 7 neste texto.** `weekly_review_text()` vira artefato no vault **e** corpo de nudge, e
o corpo inteiro do nudge aparece no lockscreen. Aqui só entra **contagem e semana** — o texto
da melhoria fica no pack, que só sai por `/review/weekly`, atrás do login. Há teste de mutação
provando que a guarda morde.

## Superfícies no app

- **Melhorias** (`Melhorias.tsx`, na Home → Ferramentas): campo de entrada com chips de
  alvo; "desta semana · YYYY-Wnn" no topo; "escolhidas antes · fez?"; "a triar · um toque";
  fila por alvo; resolvidas colapsadas. Todo card da fila traz chips `→ app / → empresa /
  → fluxo` para **re-triar**: sem eles, um toque errado mandava a melhoria para o balde
  `app` (que o review não cobra) sem caminho de volta pela UI — nem "descartar → voltar à
  fila", que não mexe no alvo.
- **Revisão**: linha da escolhida **desta semana**, ou "N paradas — escolher 1"; linha
  separada "N a triar — um toque cada"; linha das vencidas ("fez?"); linha informativa das
  de app. Toque abre a tela.
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
- [x] escolha de semana anterior NÃO é servida como "a desta semana" e o convite volta
- [x] a vencida vira "fez?" em vez de sumir (lei 3) ou travar a vaga em silêncio
- [x] `a_triar` e `escolhiveis` contados em separado: o CTA promete o que a tela oferece
- [x] `ideia:` não é gatilho — a palavra continua valendo para leitura e ditado
- [x] prefixo sem texto (`melhoria:` sozinho) não vira card em branco — idem `hack:`
- [x] o checkbox "sensível" do formulário chega ao registro
- [x] o texto de uma melhoria sensível nunca entra em `weekly_review_text()` (lei 7)
- [x] o Raw sai ANTES do hook, verbatim e com prefixo (lei 1) — asserido, não presumido

**Todas as guardas acima foram provadas por MUTAÇÃO**: cada uma foi quebrada de propósito e
o teste correspondente falhou. Nenhuma passa por acidente.

**Testes:** `bff/tests/test_melhorias.py` (44) · `bff/tests/test_edificacao.py` (guarda irmã) ·
`app/tests/melhoriasView.test.mjs` (11).
