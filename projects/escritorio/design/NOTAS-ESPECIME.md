# Notas do espécime — decisão tipográfica

Espécime: `design/especime-tipografico.html` (abrir no navegador; fontes via Google Fonts CDN).

## Recomendação

**Instrument Serif + Space Grotesk + IBM Plex Mono** (`@expo-google-fonts/instrument-serif`,
`space-grotesk`, `ibm-plex-mono` — os três confirmados no catálogo Expo).

Dois argumentos verificáveis, nenhum adjetivo:

1. **O número manda.** A base C é um placar com saldo contando ao vivo, e `font-variant-numeric`
   não é confiável no RN (iOS honra `fontVariant: ["tabular-nums"]`, Android não garante). A única
   garantia nas duas plataformas é mono por construção. IBM Plex Mono é a mono já carregada no app,
   tabular por desenho, e resolve de brinde o `+10` miúdo: mesmo desenho dos metadados, some na
   linha — discreto sem truque de cor. Hoje os heróis (`metricValue`, `nivel`, `reviewPct`) saem em
   Fraunces, de figuras proporcionais: o saldo dança.
2. **A voz sai da faixa errada.** O diagnóstico da D3 está certo e o espécime o prova em pixels:
   `Fraunces_500Medium` é uma instância estática com `opsz` travado no default (~14), usada a
   18–34px — exatamente onde ela engrossa. O Expo não expõe eixo óptico, então não há ajuste
   possível. Instrument Serif tem corte único (400 + itálico): não há eixo para errar, e o desenho
   já nasce certo nesses tamanhos. Custo: sai 1 família, entra 1; o app segue com 3 famílias
   (6 → 7 arquivos com o itálico opcional).

## Descartadas

- **Controle C (Space Grotesk 700 caps + Plex Mono)** — o mais barato (2 famílias), mas o herói em
  Space Grotesk é proporcional (dança, sem `tnum` na fonte) e o caps a 21–30px puxa para placar de
  academia. Se o Leo priorizar "2 famílias" acima de tudo, é o fallback honesto.
- **Newsreader + Inter + Plex Mono** — a serifa mais confortável a 18–21px, mas temperamento de
  jornal/revista, longe do "comando pessoal". Boa segunda opção se a Instrument parecer frágil.
- **DM Serif Display + Archivo + Plex Mono** — display de alto contraste: a 18–21px os hairlines
  somem em OLED escuro. Mesmo problema de faixa da Fraunces, sem eixo como desculpa.
- **Bricolage Grotesque + Archivo + JetBrains Mono** — personalidade real, mas flerta com o
  "chamativo" que ele rejeitou em todas as rodadas.
- **Syne + Inter + JetBrains Mono** — expandida de mostrador, cara de estúdio de design; a 21px
  ocupa largura demais e grita num app aberto 20 vezes ao dia.
- **Inter + JetBrains Mono** — o mínimo viável que garante o número (2 famílias), mas a voz
  desaparece: Inter 600 a 30px é dashboard SaaS, sem cerimônia.
- **Fraunces (controle atual)** — fonte certa na faixa errada; só faria sentido a 60px+, tamanho
  que o app nunca usa na serifa (máximo real: 34px).
