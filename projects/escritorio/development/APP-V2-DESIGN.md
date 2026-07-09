---
artifact: app-v2-design-spec
capability: escritorio-app
status: approved
approved: 2026-07-04
direction: "midnight desk" (convergência GPT/codex + Claude, iterada em mockup e aprovada pelo Leo)
scope: redesign visual (A) + expansão de telas (B). Construído contra MOCK; o "flip" pluga depois.
mockups: scratchpad/mockup3.png (Home + chat drawer), mockup-chat.png (chat 2-colunas estilo Codex/Claude)
---

# APP-V2-DESIGN — o app do escritório (redesign + expansão)

## 1. Objetivo e escopo
v2 do app: **bonito + completo + intuitivo**. Leo escolheu **A (visual/UX) + B (mais telas)**; o **C (flip /
dados reais)** fica pra depois — construímos contra o **mock atual** e, quando ligar no real (BFF → Hermes /
ClickUp), é trocar a fonte, sem retrabalho. Segue **glass-over-Hermes** (D-1): o app não guarda nada canônico.

## 2. Design system — "midnight desk"
Sensação: **uma escrivaninha à noite** — foco calmo e quente pra um founder noturno, não um SaaS. Dark-first.

### Paleta (FINAL — premium mono, aprovada "opção 2")
**DARK** (principal): bg `#0A0A0C` (preto neutro, sem tom azul) · surface `#121214` · card `#1A1A1D` ·
card2 `#151518` · text `#F4F4F5` · muted `#9A9AA2` · line `rgba(255,255,255,.08)` ·
**accent bronze `#C9A97E`** · accentSoft `rgba(201,169,126,.12)`.
**LIGHT**: bg `#FAFAF9` · surface `#FFFFFF` · card `#FFFFFF` · text `#18181B` · muted `#71717A` · accent `#A9834F`.
**Áreas** (tom médio — dessaturadas mas legíveis de relance): Trabalho `#7690BC` · Finanças `#6FB58C` ·
Saúde `#DE8A7A` · Pessoal `#A88CBE`. A base é **grayscale/preto**; a cor entra só nas áreas + o bronze.
Bolha do usuário no chat = cinza neutro elevado (`#26262C`), **não colorida**.

### Tipografia (3 papéis)
- **Fraunces** (serifa) — os "momentos": saudação da Home, títulos de modo, falas do mentor, citações do compasso.
- **Space Grotesk** — UI, headings, navegação.
- **IBM Plex Mono** — KPIs, números, timestamps, labels/tags (uppercase, letter-spacing).
Via `expo-font`. Evitar o look default Inter/Roboto/system.

### Ícones + movimento
- Set de **linha** (Lucide / Phosphor via `react-native-svg` ou `@expo/vector-icons`) — **sem emoji**. Stroke ~2px, cantos suaves.
- Movimento **contido e tátil**: 180–220ms, fade + slide suave, spring gentil. Mic com press; drawer desliza; troca de modo = "girar um dial", não trocar aba.

### Assinatura visual
Cards escuros com **hairline border** + **glow sutil na cor da área** (edge-lit); âmbar de candeeiro no accent;
serifa nos momentos; enquadramento **consciente do horário** ("Boa noite, Leo"). Premium, introspectivo, dele.

### Biblioteca de componentes (src/ui)
`Card` · `AppButton` (primary/ghost/amber) · `Field` · `Chip`/`Pill` (área e mono) · `ListRow` · `SectionHeader`
(mono) · `EmptyState` · `AreaTag` · `Drawer`/`Sheet` · `TabBar` (line icons) · `ModeSelector` · `MicButton`.
Tema light/dark por tokens (`theme.ts`) + hook (`useTheme`, segue `useColorScheme` + toggle).

## 3. Navegação
Bottom tabs: **Home · Capturar · Tarefas · Chat**. Revisão = bloco da Home (Radar) + tela ao tocar.
Tema segue o sistema (dark default) com toggle manual.

## 4. Telas
### Home — "brief da noite"
Saudação por horário (serifa) · linha de foco + **estado** ("energia baixa · clareza alta") · **3 Prioridades**
(cards por área, borda + glow, próxima ação) · **Radar** (chips mono: inbox, vencendo, nudge do mentor em âmbar)
· **Capture Dock** (voz-first, sempre à mão).
### Capturar (+ Captura de leitura)
Caixa voz/texto → resposta ("✅ anotado"). **Modo sessão de leitura**: `livro:` abre uma sessão; itens
(citação / comentário / ideia / coach) acumulam na tela; **"compilar"** finaliza → nota no vault. Segue a
gramática de captura do `CLAUDE.md` do vault.
### Tarefas (enriquecida)
Por área (4 cores), criar/concluir + **detalhe/editar**, filtro por área, recência ("última vez há X").
### Revisão (enriquecida)
Cobranças do dia por severidade (regras do cutuca/cadence) + itens **★ pra Anki**.
### Chat — estilo Codex/Claude
**Tela larga (tablet/paisagem): 2 colunas** — histórico de conversas à esquerda (agrupado Hoje/Ontem/Semana,
ponto na cor do modo, "+ Nova", busca) + a conversa à direita. **Celular em pé:** o histórico vira **drawer**.
Seletor de modo (Capturas / Mentor / Conselho / Tarefas). Mentor e Conselho com o comportamento fundamentado
(anti-bajulação, citar as notas do Leo, fechar com ação no ClickUp) — como já está nas personalities do Hermes.

## 5. Arquitetura
- **Expo / React Native**, Android-first. Tokens em `src/theme.ts` (light+dark) + `useTheme`. Componentes em
  `src/ui`. Telas em `src/screens`. Navegação: avaliar `react-navigation` (bottom tabs + o layout 2-colunas do chat).
- **Mock por ora** (`src/api` devolve dados canned); o flip liga no BFF real depois (mesma interface).
- Fontes via `expo-font`. Ícones via `react-native-svg`/vector-icons.

## 6. Fases de implementação (nesta ordem)
1. **Fundação visual** — tokens light/dark + fontes + ícones + biblioteca de componentes + aplicar nas 3 telas atuais.
2. **Home** ("brief da noite").
3. **Chat** 2-colunas + drawer (estilo Codex/Claude).
4. **Captura de leitura** (sessão).
5. **Enriquecer** Tarefas / Revisão (detalhe/editar/filtro, ★ Anki).

## 7. Fora de escopo (agora)
- O **flip** (dados reais) — mock por ora.
- **VPS / uso fora de casa** — o Telegram já cobre o mobile.
- **iPhone** — Android-first; o mesmo código serve depois.

## Nota de método
As direções vieram de **GPT (codex CLI) + Claude** em paralelo (o Gemini CLI está instalado mas sem auth nessa
máquina). Mockups renderizados com Chrome headless a partir de HTML e revisados em foto com o Leo até o "agora sim".
