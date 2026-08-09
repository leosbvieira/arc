# NOTAS-C2 — a variação C, sóbria

Resumo das decisões desta rodada. O HTML (`proposta-c2-sobria.html`) é a peça completa; isto aqui é o
índice das escolhas e das dúvidas que sobraram.

## Decisões

- **Accent: bronze `#DEB878` raro + sálvia `#71B49A`.** Nenhuma cor nova — os dois tons já existem no
  `theme.ts`. O verde-elétrico sai sem substituto. O bronze, que cobria todo botão e todo selo (e era,
  ele mesmo, o chamativo), fica restrito a um elemento cheio por tela: o primário ou a recompensa.
  Única exceção declarada: a tela de recompensa tem dois bronzes (o "+140" e o "Boa noite"), porque
  ela inteira é o momento da recompensa.
- **Tipografia com territórios que não se cruzam.** Syne = voz (título de tela, saudação,
  número-herói que chega pronto). Bricolage = UI (todo texto que se lê e toca). IBM Plex Mono =
  instrumento (todo número que se move ao vivo e todo número miúdo, incluindo o "+10" da lista) —
  porque nem Syne nem Bricolage têm figuras tabulares e o Android não garante `font-variant-numeric`.
  Syne 800 **não é carregada**: existe no espécime só como demonstração do que se evita.
- **Regra de uma alavanca.** Por elemento: tamanho grande OU caixa alta OU peso alto, nunca as três.
  Títulos: Syne 600, 22–26px, caixa baixa. Número-herói: Syne 700, 48–64px. Eyebrows continuam sendo
  o único lugar com caixa alta (mono miúda, como sempre foi no midnight desk).
- **Pontuação na tarefa = metadado.** Token novo `faint #5F626B` (um passo abaixo do muted). O "+10"
  em repouso é mono 10.5, faint, coluna de margem alinhada, sem pill/fundo/cor. No toque de concluir
  ele acende em sálvia e sobe 12px esmaecendo em 350ms (< 400ms) — recompensa é evento, não decoração.
- **Correção sobre a C:** o desconto do placar fica em muted, não em coral — a lei nº 4 do
  `Revisao.tsx` ("desconto não é erro, é fato") manda, e a C errava neste ponto.
- **Streak sem punição.** "Sequência 6 · recorde 11" no tom dos demais fatos. Após um furo:
  "sequência 1 · recorde 11", mesma cor, sem vermelho, sem culpa, recorde sempre visível.
- **Honestidade de dados.** `POINTS` local em `theme.ts` (provisória, display-only; o saldo de
  `getPontos()` sempre vence). Streak exige campo novo no BFF (`sequencia_atual`/`sequencia_recorde`)
  e por isso mora na onda 4 — ondas 1–3 não tocam backend, e a RewardSheet nasce sem streak em vez
  de mostrar número inventado.

## Dúvidas que sobraram

- **Se Bricolage + Syne brigarem na prática**, a saída barata está no espécime: Bricolage 700 cobre
  voz e número-herói, e a troca é de 2 linhas no mapa `fonts` do `theme.ts` (os papéis já estão
  isolados por token). Decisão dele, vendo a página.
- **O saldo da Home é mono, não Syne**, porque re-soma visivelmente a cada refresh
  (`AppState "active"`). Se ele preferir o saldo-herói em Syne também na Home, a regra "número que
  se move fica em mono" precisa ser relaxada — trade-off declarado, não escondido.
- **A tabela `POINTS`** eventualmente pode querer virar dado do BFF (se o Mentor ou o scorecard
  passarem a calcular por tipo de ação). Até lá, display-only e comentada como provisória.
