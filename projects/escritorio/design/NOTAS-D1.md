# NOTAS — D1 "Cofre" (metal, gravação, medalha)

## Decisões

- **Accent único mantido: bronze `#DEB878`.** A novidade cromática é só um **segundo metal** (platina `#C7CBD4` / `#7E828C`, dessaturado) para valores potenciais, descontos e números de apoio. Contraste por temperatura de metal, nunca por segundo hue. `bronze-deep #8C6B3F` entra como sombra do bronze (bordas, quinas, fileira de marcas).
- **A gamificação da C foi herdada inteira** (pontos na linha, "vale +N" no hero, saldo em escala, total do dia à vista) e revestida em material: número gravado (text-shadow em duas direções), bisel de 1px, borda dupla, medalha em baixo-relevo, folha metálica só em barras e no botão-tranca. Nada de verde, glow, pill de pontos ou vocabulário de HUD.
- **Streak = fileira de marcas cinzeladas** com três estados: cheia / cavidade / tracejada (futuro). A quebra é uma cavidade escura — visível, muda, sem vermelho e sem texto punitivo. "Atual 6 · melhor 21" dá os dois números sem drama. É a lei nº 4 do código (placar informa, não julga) em geometria.
- **Fraunces sai, Archivo Expanded entra** (eixo `wdth 125`, pesos 700/800) para algarismos e títulos; Inter para UI; IBM Plex Mono fica para eyebrows e miúdos. As três existem no Google Fonts e em `@expo-google-fonts`. Defesa: serifa é território editorial (D3); o cofre pede largura de mostrador e precisão. Espécime mostra o número em 800 vs 500 — o 500 perde a presença de cunhagem.
- **RitoButton existe exatamente duas vezes no app** (Fechar o dia, Fechar a semana no vault). Restrição deliberada: se todo botão é chapa de bronze, nenhum é.
- **Desconto em platina apagada, nunca danger.** No placar, `−30` é metal frio; o vermelho fica reservado a erro real e severidade de tarefa.

## Honestidade de dados (custo declarado)

- **Pontos por tipo de ação não existem no app nem no BFF.** Proposta: tabela local em `theme.ts` (`POINTS`), marcada como provisória no código, até o BFF expor. O saldo real continua vindo do servidor; os valores por linha são "estimativa da casa".
- **Streak corrido exige campo novo no BFF** (série diária + contadores atual/melhor; `semanal.dailies` dá a base). É a onda 5, a única com backend. Antes dela, a fileira mostra só a semana corrente, com rótulo honesto.

## Dúvidas que sobraram

- **Tamanho da tabela de pontos.** 10/15/30 por esforço de tarefa exige classificar a tarefa — hoje não há campo de esforço. Alternativa mais simples: valor único por tipo (tarefa +15), sem julgar tamanho. Tentei as duas no papel; a única é mais coerente com "um toque resolve", mas empobrece a hierarquia.
- **Archivo expandido no Expo.** O eixo `wdth` existe na família variável do Google Fonts; se o pacote `@expo-google-fonts/archivo` não expuser as instâncias expandidas, o plano B é usar Archivo 800 normal com `letterSpacing` negativo (perde a largura de mostrador, mantém o peso).
- **Animação do "+N" viajando ao cofre do dia** depende de o contador estar visível na viewport; em listas longas ele some do topo. Não resolvido: ou o chip fica fixo (sticky) ou a animação vira um flash local na linha.
- **Gravação em RN** é `textShadow*` nativo — funciona, mas sombras de texto no Android são mais fracas; pode ser preciso duplicar o offset para o relevo ler igual nos dois alvos (só há um alvo real: o Android dele).
