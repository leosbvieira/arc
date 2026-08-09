# Notas — variação B (clara)

Resumo das decisões da proposta `proposta-visual-kimi-clara.html` e do que ficou em aberto.

## Decisões

- **Base real, não inventada.** A paleta é a `light` de `app/src/theme.ts:44-62`, que existia sem
  uso. Três acréscimos, todos pelo mesmo motivo: bronze `#A9834F` (3.5:1), danger `#C56A5A` (3.8:1)
  e success `#4E9A72` (3.4:1) sobre branco reprovam em 4.5:1 para texto. Nasceram
  `primaryDeep #966F3E` (botão primário, 4.55:1 com branco), `primaryInk #7C5F33` (texto pequeno,
  5.9:1), `dangerInk #A34A3D` e `successInk #3A7A58`. Os originais ficam para ícones, fios e barras.
- **Outra gramática, não a A pintada de branco.** Hierarquia por tipografia e régua de 1px; cartão
  branco só para objetos reais (comprovante, folha de captura, próxima ação, formulário de
  check-in); sombra proibida; bronze raro (primário + dígitos de pendência). O nome "Leo." perdeu o
  bronze e ganhou itálico serif.
- **Recompensa própria: comprovante carimbado.** Glow não existe no claro, então o fim do rito vira
  um recibo de escritório (borda picotada, totais com dot leaders, dados reais de `getPontos()`)
  com o carimbo `RewardStamp` — círculo de borda dupla, −7°, entrada com `Animated` scale. Nada
  emprestado do selo da variação A.
- **"Ferramentas" vira Índice.** Sumário com pontilhado, agrupado em Ritos / Filas / Rotina, com
  pendência em dígito à direita usando os sinais que a Home já carrega. Zero fetch novo.
- **Fechar o dia:** um `RitualButton` de 56px sempre habilitado (o código já grava cada rotina no
  toque), despejo recolhido a linha opcional, régua de progresso "N de M ritmos".
- **Quando cada tema serve** está declarado no masthead: claro = manhã/mesa/sol; escuro (A) = ritos
  da noite. A onda 4 liga o toggle com padrão por horário (claro 5h30–19h) e override em Ajustes.

## Dúvidas que sobraram

- **O toque das 5h30 da Abertura** ficou descrito, não mockado (o frame mostra o estado com
  template). Vale um mockup próprio na revisão com o Leo?
- **Índice: seção no fim da Home ou tela separada?** Modelei como tela (com tabbar) e como seção;
  as duas cabem. Decidir no uso real — a seção "Precisa de você" pode bastar no dia a dia.
- **Cores de área no claro:** mantive as 10 de `AREA_COLORS` (calibradas para o dark) como fios de
  2–2.5px. Sobre branco algumas ficam claras demais para texto — por isso nunca carregam texto no
  desenho. Se um dia virarem texto, precisam de uma passada de escurecimento igual à do bronze.
- **Picote do comprovante em RN:** em CSS é trivial; em `View` nativo sai por SVG ou por duas
  bordas tracejadas. Aceitável simplificar para borda reta dupla se custar caro — o carimbo é quem
  carrega a metáfora.
- **Tab "Hoje" usa o ícone `circle` no código atual** — mantive os rótulos da tabbar como estão;
  revisar ícones Feather ficou fora do escopo.
