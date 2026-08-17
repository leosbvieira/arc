# NOTAS — nome & marca do Aeternum

Resumo das decisões e das dúvidas que sobraram. A peça principal é `proposta-logo-aeternum.html`.

## Decisões

- **Nome: Aeternum — travado e aprovado.** O que faltava era a forma: o `app.json`
  ainda exibe o nome de trabalho "escritório" e não existia forma gráfica do nome.
  Display name do app = **Aeternum**; palavra-marca = **ÆTERNUM** em **Michroma** —
  Æ em bronze `#DEB878` + TTERNUM em branco `#F4EFE7`. No texto corrido e na UI,
  "Aeternum"; o Æ e o Michroma são a forma desenhada da marca (as fontes de
  interface do app — Syne/Bricolage — não mudam).
- **Marca: o Æ da palavra-marca (rev 4).** O monograma é **o glifo real da ligadura Æ
  do Michroma**, extraído da TTF — o ícone é literalmente o começo de "ÆTERNUM":
  mesmo glifo, mesma fonte. **Monograma canônico: branco `#F4EFE7` sobre midnight
  `#0C0F13`** (decisão do Leo: "o logo, mas em branco"); o bronze fica reservado ao Æ
  da palavra-marca e à ação primária do app. **Ícone do app: a inversa** — Æ midnight
  `#181108` sobre branco `#F4EFE7` (escolha do Leo na revisão; adaptive icon =
  foreground midnight + background `#F4EFE7`). Histórico: rev 1 (ligadura Æ desenhada
  à mão), rev 2 (AE geométrico) e rev 3 (AE do Syne 700) descartadas — todas eram
  *desenhos de* AE, não *o* AE/Æ da palavra-marca; a rev 4 resolve extraindo o glifo
  da própria fonte da marca, apontada pelo Leo na referência visual.
- **Fonte da marca:** Michroma (SIL OFL 1.1). `Michroma-Regular.ttf` +
  `OFL-Michroma.txt` ficam em `design/`; o `gerar-marca.py` extrai os glifos e
  regenera SVGs e PNGs (deps: `pip install pillow fonttools`).
- **Anel do loop fica como marca cerimonial** (fechamento de ciclo/review anual) —
  nunca como ícone do app.
- **Tagline: "Nada se perde."** Uso raro (proposta, capa de review) — não vai no boot.
- **Arquivos-fonte da marca ficam em `design/`:** `aeternum-mark.svg`,
  `aeternum-icon.svg`, `aeternum-wordmark.svg`, `aeternum-loop.svg`, PNGs
  (`-icon-1024`, `-mark-1024`, `-adaptive-fg-1024`, `-wordmark`) e o gerador.

- **Ligado no app (2026-08-09).** `app.json`: `"name": "Aeternum"` (era "escritório"),
  `"icon": ./assets/icon.png`, `android.adaptiveIcon` (foreground midnight +
  background `#F4EFE7`); `expo-splash-screen ~31.0.13` instalado e plugin configurado
  (`splash-icon.png`, imageWidth 200, fundo `#080A0D`). Assets em `app/assets/` =
  cópias dos PNGs de `design/`. Config validada com `npx expo config --type prebuild`.
  **Ícone e splash só aparecem num novo dev build** (EAS / `run:android`) — não no
  build já instalado. Slug e package ficaram (identificadores técnicos).

## Dúvidas que sobraram
- **Michroma dentro do app?** Se a palavra-marca aparecer como texto na UI (ex.:
  Ajustes), embutir a TTF via expo-font; caso contrário, usar os assets exportados.
  Decisão fica para a leva de implementação.
- **Ícone de notificação do Android** (status bar, monocromático): a silhueta do Æ já
  serve; se o sistema achatar mal, gerar variante dedicada na leva de assets.
- **Colisão AeternumFintech**: sem ação por ora (contextos separados); o monograma Æ é
  o diferenciador sem trocar o nome.
- **Variante clara** (fundo claro/impressão): é a inversa já documentada (Æ midnight
  sobre branco); se precisar de arquivos, o gerador ganha um flag de cores.
