---
artifact: skill-spec
capability: escritorio
skill: reading-staging (lane "Leitura")
status: proposed
date: 2026-07-16
source_refs:
  - CAPTURE-GRAMMAR-SPEC.md
  - AETERNUM-SPEC.md
  - "brainstorm 2026-07-16 (Leo + Claude): staging da nota de leitura"
engine: Hermes (profile "Leitura")
implements: "portão humano de aprovação entre compilar e gravar no vault"
---

# SKILL SPEC — reading staging (lane "Leitura")

Insere um **portão humano** entre "compilar a nota" e "gravar no vault". Hoje `compilar`
publica no Obsidian **sem você ver**. Esta spec faz o Hermes gerar a nota, mostrar em
**preview read-only**, e só gravar no vault quando **você aprovar**.

Coerente com a lei de fidelidade: você **não edita** o texto — só **aprova ou rejeita**.
O vault continua derivado byte-a-byte do buffer que você ditou. Rejeitar volta a sessão
pras notas cruas, onde você corrige e recompila (o Hermes é LLM: recompilar pode gerar
outra versão — esse é o valor do "rejeitar").

**Simetria que motivou a spec:** os cards Anki já têm staging (tela Revisão: sugerido →
aprovado). A *nota* — o artefato permanente do segundo cérebro — não tinha. Agora tem.

## Decisões (brainstorm 2026-07-16)
- **D-A — preview read-only.** Aprovar/rejeitar; **sem edição no app**. Mantém a fidelidade
  e é o mais simples. (Editar inline foi descartado: viraria você a fonte da verdade em vez
  do buffer, quebrando a garantia do `source_digest`.)
- **D-B — rejeitar volta a `pending`.** Buffer intacto; você mexe nas notas cruas **ou** só
  recompila. Um caminho de volta só, reusando o ciclo `pending → compilar` que já existe.
- **D-C — preview inline na Captura, na hora.** Revisa enquanto a leitura está fresca.
  Recuperável de graça: o `draft_md` persiste no servidor; a sessão reaparece nas listas de
  pendência que já existem.
- **D-D — Anki depois da aprovação.** Sem mudança de ordem: os cards já nascem da nota
  compilada (`_reading_notes`), não do buffer. O preview mostra **só a nota**. Sem staging duplo.

## Representação: "staged" é implícito, não um status novo

O estado "nota gerada, ainda **não** no vault" **já existe** no código como
`status='pending' AND draft_md IS NOT NULL` — é exatamente o que sobra hoje quando o vault
falha no meio do compile (coberto por teste), e o **congelamento de edição do buffer já está
ligado a ele** (`append/update/delete_last_reading_buffer` recusam com `reading_draft_ja_gerado`
quando `draft_md` não é nulo).

Reusar essa costura, em vez de criar um status `staged` novo, evita mexer em
`list_pending_reading_sessions`, na stale-reclaim (`claim_reading_compile`/`init_db`), no
`reconcile`, no `discard` e na união de status do draft local do app. A feature vira:
**partir o `/compile` atômico em dois**, com um portão no meio.

## Ciclo de vida

```
pending (draft_md = NULL, buffer editável)
   │  Compilar → POST /draft   (Hermes gera; salva draft_md; status segue 'pending')
   ▼
STAGED  ≡  pending + draft_md   (buffer CONGELADO; app mostra o preview read-only)
   ├─ Aprovar  → POST  /compile → [compiling] → grava vault + Anki + purge → compiled
   └─ Rejeitar → DELETE /draft  → limpa draft_md → volta a editável (pending puro)
```

- **`compiling`** continua sendo só o **lock transitório** durante o Hermes (no `/draft`) ou a
  escrita no vault (no `/compile`) — reusa `claim_reading_compile`.
- Falha do vault no `/compile` → `release_reading_compile` volta a `pending` **mantendo o
  draft_md** = continua STAGED; o retry reusa o draft (idempotente).

## Superfície & fluxo (glass over Hermes)

```
tela de Captura (notas cruas no buffer)
     │  toca "Compilar" (informa página final, igual hoje)
     ▼
POST /reading/sessions/{id}/draft   → Hermes gera markdown; salva draft_md + source_digest
     ▼
PREVIEW inline read-only na Captura: markdown rolável + livro/páginas/nº de notas
     ├─(Salvar no vault)─▶ POST  /reading/sessions/{id}/compile  → vault + Anki + limpa buffer
     └─(Rejeitar)────────▶ DELETE /reading/sessions/{id}/draft   → limpa draft; volta a editável
```

## API (BFF)

| Endpoint | Faz | Transição | Erros |
|---|---|---|---|
| **`POST …/draft`** *(novo)* | Claim → Hermes → salva `draft_md` + `source_digest` → devolve o markdown. **Idempotente:** draft salvo com digest batendo → devolve sem re-chamar o Hermes. **Sem vault.** | pending → pending+draft | 502 `reading_compile_indisponivel` (Hermes caiu → segue `pending`, nada perdido); 409 se `compiling`/`compiled`/`discarded`; 422 `pagina_final_invalida`/`reading_buffer_vazio` |
| **`POST …/compile`** *(vira "Aprovar")* | **Exige** `draft_md`. Revalida `source_digest` vs. buffer. Grava vault, registra a sessão de tempo, gera Anki, limpa buffer. | pending+draft → compiled | **422 `reading_draft_ausente`** se não há draft; 409 `reading_draft_snapshot_divergente` se o buffer/página mudou; 502 se vault caiu (**segue STAGED**, retry reusa) |
| **`DELETE …/draft`** *(novo, "Rejeitar")* | Limpa `draft_md` + `source_digest`. **Buffer intacto.** | pending+draft → pending | 409 `reading_compile_em_andamento`/`reading_session_compiled`; no-op idempotente se já `pending` puro |

**Refactor no `/compile`:** remover o ramo "gera o draft se faltar" (a geração migra pro `/draft`);
`/compile` passa a **pressupor** o draft. Todo o resto (vault idempotente, `add_session`,
`finish_reading_compile`, Anki, `purge_reading_content`) fica igual.

## Store / dados
- Colunas `draft_md` e `source_digest` **já existem** — sem migração.
- Novas funções: `stage_reading_draft` (grava draft + volta status a `pending`) e
  `reject_reading_draft` (limpa draft, buffer intacto). `save_reading_draft`,
  `list_pending_reading_sessions`, `claim/release/finish_reading_compile`, guards de buffer e
  `discard_reading_session` — **inalterados**.

## App (React Native)
- `readingApi.ts`: `ReadingSession` ganha `draft_md?: string | null`; novas
  `draftReadingSession(id, {pagina_final})` e `rejectReadingDraft(id)`; `compileReadingSession`
  vira o "aprovar".
- `Capture.tsx`: novo estado `preview`; "Compilar" chama `/draft`; bloco de preview read-only com
  **"Salvar no vault"** / **"Rejeitar"**; edição **congelada** enquanto há preview (bate com o
  servidor); restore-on-open mostra o preview se a sessão vier com `draft_md`.
- Sem status local novo: staged é rastreado só pelo `preview` + o `draft_md` remoto (evita que o
  `loadReadingDraft`, que valida `active|pending`, derrube o rascunho).

## Integridade & falhas (de brinde)
- **Draft velho:** `source_digest` (que já existe) trava aprovar um draft que não bate mais com o
  buffer → força recompilar. `pagina_final` entra no digest, então o campo fica congelado no preview.
- **Rede mais segura que hoje:** o draft é salvo **antes** da aprovação. Hermes cair → `pending`,
  nada perdido; vault cair → STAGED, retry reusa.
- **Anki pendente:** inalterado — se a sugestão falhar após o vault confirmar, a nota está gravada e
  o app preserva o rascunho local pra retry seguro.

## Fora de escopo (YAGNI)
Editar o markdown no app (D-A) · rejeitar = recompilar num toque (D-B) · aprovar a nota só na aba
Revisão (D-C: a recuperação já a exibe lá, mas a aprovação é inline) · preview dos cards Anki junto
da nota (D-D).

## Aceite
- Compilar mostra a nota em **preview** antes de qualquer coisa ir pro vault. ✅
- Nada é gravado no Obsidian sem **aprovação** explícita. ✅
- Rejeitar volta às notas cruas com o **buffer intacto**; recompilar funciona. ✅
- Fechar o app em STAGED **não perde** a nota — ela reaparece pra retomar o preview. ✅
- Cards Anki continuam nascendo **só depois** da nota aprovada. ✅
- Nenhuma migração de schema; o texto no vault continua **fiel** ao ditado. ✅
