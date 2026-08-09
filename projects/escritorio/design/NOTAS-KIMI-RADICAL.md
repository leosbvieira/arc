# Notas — Variação C (Ruptura): "HUD de jogo"

## A direção, em uma frase

O sistema de pontos/nível/ciclo que hoje vive escondido na aba Revisão sobe à superfície e **vira a interface inteira**: números enormes, verde-elétrico saturado, botões com peso físico de tecla, e cada ação do Leo devolvendo pontos visíveis no instante.

## Decisões centrais

- **Por que jogo e não terminal/brutalista ou "uma pergunta por vez":** o app *já é* um jogo por dentro (`saldo_total`, `nivel`, `ciclo`, `semana.ganho/desconto`, diamantes — tudo existe em `Revisao.tsx`). A ruptura mais barata e mais alinhada ao procrastinador é revelar isso, não inventar outra metáfora. Terminal serviria ao detalhista, mas não resolve "fechar devolve"; "uma pergunta por vez" esconderia as filas, aumentando a energia de descoberta.
- **Fraunces e bronze saem.** É o custo da ruptura: a serif + `#DEB878` são a alma da variação A. Entra Space Grotesk 700 em caixa alta + IBM Plex Mono como textura de console (ambas já carregadas no `useFonts`; Fraunces sai do pacote). `AREA_COLORS` ficam intactas — churn nelas seria vaidade, não ruptura.
- **Os seis princípios não foram negociados:** BigAction único e sempre habilitado no fechamento; escrever virou bônus "+40", nunca portão; um elemento volt por tela; pendência sempre com número; recompensa em número de 64px; quatro componentes (QuestRow, BigAction, SegmentBar, RewardSheet) cobrem todas as telas.
- **"Ferramentas" vira "A Mesa"**, 5ª aba da tabbar: lista ordenada por pendência (pendência > rito > arquivo), com contadores vindos dos `HomeSignals` que a Home já busca. Nenhum endpoint novo nas ondas 1–3.
- **Implementável no stack real:** sombra dura em vez de blur, animações de contagem/preenchimento com `Animated.timing` puro, gradiente só onde a Home já usa `expo-linear-gradient`. Nada de reanimated, nada de lib nova.

## Dúvidas que sobraram

1. **Pontos por ação ("+20", "+80")**: o BFF expõe saldo/nível/ciclo, mas não vi tabela de pontos por tipo de ação no app. Proposta: tabela local em `theme.ts` até o BFF expor (marcado como custo explícito na onda 4). Se os valores reais forem outros, só a tabela muda.
2. **Streak ("sequência de 6 dias")**: derivável de `semanal.dailies` no agregado, mas a sequência corrida provavelmente pede um campo novo no BFF. Tratei como bônus opcional — a RewardSheet funciona sem ela.
3. **Volt às 21h**: um "+140" elétrico antes de dormir é estimulante demais? Nomeei o risco na seção de sacrifícios, com mitigação (âmbar noturno) se incomodar na prática.
4. **Lei de Goodhart de bolso**: pontuar tudo pode incentivar "farmar" capturas. Mantive a regra do código (placar informa, não julga; pontos nunca descem), mas é uma tensão real desta direção — vale revisão depois de um mês de uso.
5. **Voltar da subtela**: hoje o chevron volta sempre para Home; com a Mesa na tabbar, propus voltar para a Mesa. Detalhe de navegação que só um teste no polegar confirma.
