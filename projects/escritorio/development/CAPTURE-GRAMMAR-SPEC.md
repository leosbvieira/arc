---
artifact: skill-spec
capability: escritorio
skill: reading-capture (lane "Leitura")
status: baseline
source_refs: [DECISIONS.md, ARCHITECTURE.md, "claude.ai reading-system chat 2026-06-30"]
engine: Hermes (profile "Leitura")   # same grammar reused by Claude Code for deep restructure
---

# SKILL SPEC — reading capture (lane "Leitura")

Turns spoken reading notes into structured markdown in the vault. **Engine-agnostic:** the
same grammar is used by Hermes (daily capture) and by Claude Code (occasional deep restructure).
This file is also the seed for the vault's `CLAUDE.md`.

## Surface & flow (glass over Hermes — D-1, D-11)
```
Wispr (voz) → tela de captura (app próprio / ponte: Telegram)
     │  texto
     ▼
Hermes, profile "Leitura"   ← parse dos 6 modos, mantém sessão
     │  GitHub MCP
     ▼
vault: /Leituras/YYYY-MM-DD — <Livro>.md   (append por fala; "compilar" finaliza)
     ├─ melhores itens → Anki (retenção)
     └─ itens de "lista" → app de compras (NÃO entram na nota)
```
The capture surface only sends text. Structuring + vault writes happen in Hermes. Switching
surface (Telegram → app próprio) changes nothing below the surface.

## Sessão
- `livro` **abre** a sessão (define contexto: título, página, hora de início).
- Cada fala seguinte **anexa** à nota do dia.
- `compilar` **finaliza**: fecha metadados (hora fim, páginas lidas, contadores), promove itens
  marcados pro Anki, roteia `lista` pro app de compras.

## Os 6 modos (voz → markdown)
| Modo | Você fala | Vira no vault |
|---|---|---|
| **livro** | "livro: Antifrágil, página 85" | frontmatter/metadados da sessão (título, página inicial, hora) |
| **comentário** | "comentário: isso liga com opcionalidade…" | `> [!note] Comentário` (teu pensamento) |
| **citação** | "citação: o que não te mata te fortalece" | `> [!quote] p.NN` — **verbatim, não reformular** (ver ⚠️) |
| **coach** | "coach, Fulano: …" | `> [!info] Fulano` (fala de outra pessoa — exige o nome) |
| **ideia** | "ideia: explorar teoria dos jogos aqui" | `> [!todo] Ideia` (flag pra aprofundar depois) |
| **lista** | "lista: comprar café" | **sai da nota** → app de compras (ou `_inbox/compras.md`) |

## ⚠️ Fidelidade da citação
Wispr limpa/reformula a fala. Pra `citação` isso é risco (muda o texto do autor). Regra: no modo
citação o Hermes **preserva verbatim** o que veio; não "melhora". Testar no trial do Wispr; se ele
reformular demais, ditar citações devagar/soletrando ou usar um marcador de fim ("fim de citação").

## Template da nota de leitura
```markdown
---
tipo: leitura
livro: "Antifrágil"
data: 2026-06-30
inicio: "21:10"
fim: "21:48"
paginas: "85-102"
tags: [leitura, antifragil]
---
# Antifrágil — 2026-06-30

> [!quote] p.88
> o que não te mata te fortalece

> [!note] Comentário
> opcionalidade ≈ ter upside sem downside simétrico

> [!todo] Ideia
> conectar com teoria dos jogos

> [!info] Coach — Fulano
> "…"
```

## Retenção (ranking / memória frequente)
- Promoção pro **Anki**: `citação` + `comentário` marcados com `★` (ou modo "anki: …").
- O que promove = config; default: tudo com `★` vira flashcard (frente/verso derivados pela nota).
- **Lembrete de revisão** = cron do Hermes ("revisa 3 notas hoje") — reaproveita o motor de nudge.
- Anki é o dono da repetição espaçada (glass-not-store: a nota mora no vault, o card no Anki).

## Config
```yaml
vault_path: "Leituras/"
nota_por: "sessao"            # uma nota por sessão de leitura
promover_anki_se: "marcado_estrela"
lista_destino: "app_compras"  # ou "_inbox/compras.md"
citacao_verbatim: true
```

## Engine notes
- **Hermes (diário):** profile "Leitura" com esta grammar no system prompt + GitHub MCP.
- **Claude Code (ocasional):** mesma grammar via o `CLAUDE.md` do vault, pra reorganização profunda
  de muitos arquivos (OAuth, custo zero — D-5). É o passo "estruturar melhor depois".

## Aceite
- Falar os 6 modos numa sessão → nota única, formatada, com metadados corretos no vault. ✅
- `citação` mantém o texto verbatim. ✅
- `lista` sai da nota pro destino de compras. ✅
- Itens `★` viram flashcards Anki; cron do Hermes lembra da revisão. ✅
- Trocar a superfície (Telegram → app próprio) não muda a nota gerada. ✅
