# NOTAS — D3 · Noturno editorial

**Entregável:** `design/proposta-d3-editorial.html` (autocontido, fallbacks de fonte declarados).

## Decisões

- **Fraunces sai, Instrument Serif entra.** Fraunces é fonte de eixo óptico: brilha a 60px+ com
  `opsz` alto e eixos SOFT/WONK. O app carrega uma instância estática (`Fraunces_500Medium`) e a usa
  a 18–34px, onde ela engrossa e fica “fofa” — é essa a sensação de “tipografia não muito boa”.
  Ajustar o eixo no stack real não existe: `@expo-google-fonts` entrega instâncias estáticas por
  peso, sem `opsz`. Newsreader foi descartada por ser serifada de texto (oldstyle figures brigam com
  placar). Instrument Serif tem um peso só (400 + itálico) e voz por contraste, não por peso —
  existe no Google Fonts e em `@expo-google-fonts/instrument-serif`. Custo: `fonts.serif` em
  `theme.ts` + imports de `App.tsx`. A prova visual (mesmo número em Space Grotesk 700 / Fraunces
  500 / Instrument Serif 400) está no espécime.
- **Regra das duas vozes numéricas:** número que atualiza ao vivo (saldo contando, tally do dia) é
  IBM Plex Mono tabular — dígito não dança. Número que chega pronto (+140 da recompensa, saldo-herói)
  é Instrument Serif grande. As duas nunca dividem a mesma linha.
- **O jogo é notação, não HUD:** pontos em coluna de margem fixa (mono 10.5–12px, muted antes /
  bronze depois, herda danger quando atrasada), tally do dia como fio entre Tarefas/Fechar/Home,
  placar como livro-razão (LedgerRow, fio de cabelo). Gesto de concluir: um toque → ponto sobe da
  margem ao tally + UndoToast (sai a confirmação-inline de `Tasks.tsx`).
- **Streak sem punição:** fileira de dias com círculo oco no furo, contador honesto (“dia 1 de uma
  nova sequência”) e recorde sempre visível — lei nº 4 do código virando forma gráfica. Renderizado
  na galeria de componentes.
- **Preços:** tabela local `POINTS` em `theme.ts` (captura 5, tarefa 10, atrasada 15, ritmo 20,
  diário 40) — display-only até o BFF expor; o saldo oficial de `getPontos()` sempre vence.

## Dúvidas que sobraram

- **Instrument Serif em RN:** figuras são lining proporcionais — por isso contadores vivos ficaram
  no mono. Se algum algarismo-herói animado (contagem 0→140) incomodar por largura variável, a
  contagem passa a acontecer no mono e o serif só entra no valor final.
- **Tarefa atrasada pagando mais (+15):** incentiva resgate, mas pode premiar procrastinação
  (deixar atrasar para valer mais). Mitigação possível: bônus só na primeira vez que atrasa, ou
  teto semanal de pontos de resgate. Deixei simples; vale uma decisão do Leo.
- **Streak corrido** depende de campo novo no BFF (`pontos.sequencia`); estimei 0.5–1 dia +
  migração. Até lá, a fileira mostra os últimos ~12 dias pelo histórico semanal — aproximação que
  quebra acima de 12 semanas. A recompensa da onda 3 não fica refém: sem o campo, a linha some.
- **Badge do Painel (8)** soma dívidas de naturezas diferentes (triagem + Anki + leituras); se a
  soma parecer artificial, o badge vira só o total da triagem, que é a fila mais sensível a prazo.
