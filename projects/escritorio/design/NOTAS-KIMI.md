# NOTAS — proposta de redesenho (Kimi)

Resumo das decisões e das dúvidas que sobraram. A peça principal é `proposta-visual-kimi.html`.

## Decisões

- **Nada de tokens novos na base.** Paleta, tipografia, espaçamento e raio do `theme.ts` ficam
  intocados — a base “midnight desk” é boa. Os únicos acréscimos: alvo mínimo de toque de 44px
  (hoje os ritos têm alvos de 28–34px) e um gradiente bronze (`expo-linear-gradient`, já
  instalado) reservado ao botão primário de rito, para que ele seja inconfundível sem competir
  com o `AppButton` comum.
- **Fechar o dia é a onda 1.** O código já tem o comportamento certo (check otimista via
  `checkRoutine`, modo mínimo sem texto) — o que falta é superfície: os links de texto viram um
  `RiteButton` + link opcional, os ☐/☑ viram `CheckRow` de 56px, e o estado `done` vira um
  `RewardSeal` com saldo, delta de pontos e barra do ciclo (tudo já vem do `getPontos()`; o
  delta diário é a única informação nova).
- **“Ferramentas” vira a aba Painel (5ª aba, ícone `grid`).** Lista ordenada por dívida, com
  contadores reais (`getTriagem().n`, `mais_velho_d`, Anki sugeridos, sessões de leitura) e
  badge na tabbar. Escolhi aba em vez de sheet/menu porque o badge precisa estar visível de
  qualquer lugar do app — sheet esconde o sinal.
- **Concluir tarefa sem confirmação**, com `UndoToast` de ~5s. A faixa “CONCLUIR TAREFA?” atual
  é fricção no gesto mais frequente da Central de Execução.
- **Mentor (Chat) não foi redesenhado.** Já é uma das telas boas (modos Mentor/Capturas/Conselho
  com prompts); recebe só herança de tokens. Mexer nela agora seria gastar onde não dói.

## Dúvidas que sobraram

- **Delta de pontos do dia (“+45 hoje”)**: o `getPontos()` devolve saldo/nível/ciclo; o delta
  exato do fechamento pode exigir um campo a mais no BFF ou cálculo por diferença de saldo.
  Se não vier fácil, mostrar só o saldo novo — não bloqueia a onda 1.
- **Desfazer conclusão de tarefa**: depende de existir endpoint de “reabrir”. Se não existir,
  o toast vira apenas confirmação visual e a confirmação prévia permanece (decisão de backend,
  não de desenho).
- **Badge na tabbar exige prefetch** dos sinais fora da Home (hoje a Home os busca). Custo
  pequeno, mas é um ponto de arquitetura: os sinais podem subir para um store no `App.tsx`.
- **Nomes de rotinas nos mockups são ilustrativos** (“Corrida 5 km”, “Skincare da noite” — o
  segundo vem do placeholder real de `Rotinas.tsx`). Os dados reais vêm do BFF por template
  (yoga/corrida) e dia da semana.
- **Agenda**: a Home hoje aponta “abrir agenda” para a Abertura e o comentário no código admite
  que o rótulo mentia (o `GET /agenda` segue órfão). Mantive a entrada “Agenda” no Painel com o
  nome honesto e conteúdo de amanhã; quando a tela de calendário existir, o Painel já tem o slot.
