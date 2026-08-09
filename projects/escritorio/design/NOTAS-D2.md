# NOTAS — D2 · Instrumento (painel de precisão)

## Decisões

- **Accent trocado: bronze `#DEB878` → aço `#8FB6C4`.** O Leo rejeitou o chamativo; o bronze quente em
  todo botão e selo era o chamativo da A. O aço-petróleo dessaturado conduz ações e leituras com
  contraste ≈ 8:1 sobre `#080A0D`. O bronze não some — vira **detalhe raro** (a marca "hoje" na fita
  e o ◆ de nível), o que devolve o valor que a saturação tirava. Dois tons de accent, como manda o briefing.
- **Tipografia: Martian Mono (números/eyebrows) + Inter Tight (texto), zero serifa.** Fraunces sai.
  Martian Mono é mono de verdade: figuras tabulares por construção — o saldo não dança ao atualizar,
  que era a reclamação central. Inter Tight troca Space Grotesk por terminais mais apertados e menos
  "startup". Ambas existem no Google Fonts e em `@expo-google-fonts` (`martian-mono`, `inter-tight`).
- **Nada preenche área grande.** Tudo é fio de 1px, tick e algarismo. A única exceção por tela é o
  botão primário (BigAction), que carrega a soma otimista no rótulo ("garante +65").
- **Streak = strip chart contínuo.** Dia fechado = pulso; dia sem registro = vazio com régua
  pontilhada em danger a 55% (informa, não acusa); o traço continua depois do vazio. A quebra é um
  fato geométrico, não um evento a perdoar — é assim que ela é comunicada sem punir, mantendo a lei
  "pontos nunca descem". Mesmo componente (`StreakTape`) na recompensa do Fechar e no Placar.
- **Placar como mostrador:** saldo 60px tabular, régua de ciclo com agulha de 1.5px, ganho em
  success / desconto em muted, padrões em mono mudo. Todos os dados já existem em `Revisao.tsx`;
  herda a ambição da C sem a voltagem.
- **"Ferramentas" → "Painel":** lista numerada agrupada por estado ("esperando você · ritos ·
  referência"), com os sinais que a Home já calcula (`staging/anki/reading`) e o estado dos ritos.

## Custos declarados (não é de graça)

- **Pontos por tipo de ação:** não existe no BFF. Onda 2 usa tabela local `POINTS` em `theme.ts`
  (marcada como provisória); onda 4 expõe no BFF e aposenta a tabela.
- **Streak corrido (28 dias):** `semanal.dailies` dá só a semana. A fita completa exige campo novo
  no `/pontos` (ex.: `fechamentos: number[]`). Até lá, a fita renderiza a semana corrente —
  as ondas 1–3 não dependem do backend.

## Dúvidas que sobraram

- **Tom exato do steel:** `#8FB6C4` foi escolhido a olho para ≈ 8:1 de contraste; vale um ajuste
  fino no aparelho real (Android, brilho noturno) — frio demais pode parecer clínico.
- **Pontos de rotina vs. tarefa:** a tabela local chuta 5–15 por peso, mas a calibragem real é do
  Leo — os números da proposta são ilustrativos, não normativos.
- **Fita sem streak do BFF:** renderizar só 7 dias muda a leitura do componente (vazio curto parece
  sequência nova). Se a onda 4 atrasar muito, considerar esconder a fita até haver janela de 28d.
- **Danger pontilhado na quebra:** é o uso mais "quente" permitido fora de severidade; se incomodar,
  a régua do vazio pode ir para muted — o vazio em si já comunica.
