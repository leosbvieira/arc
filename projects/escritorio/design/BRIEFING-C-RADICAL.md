# Briefing C — variação de RUPTURA

Leia primeiro `BRIEFING.md` (nesta mesma pasta). **Continuam valendo**: quem é o Leo (detalhista +
procrastinador), o stack real (React Native / Expo 54, ícones Feather, `Animated` puro, sem
biblioteca de UI), os problemas conhecidos, a estrutura do documento (princípios → mockups →
antes/depois → sistema → ondas) e as telas obrigatórias (Fechar o dia, Home, substituto de
"Ferramentas", Abertura, Captura).

Este arquivo diz **o que muda** — e aqui muda muito.

## O que já existe

- **Variação A** (`proposta-visual-kimi.html`): escura, "midnight desk", premium mono, sóbria.
  Aprovada.
- **Variação B** (sendo feita em paralelo): clara, editorial/papel, calma, muito espaço em branco.

## Sua tarefa: ser genuinamente outra coisa

Esta variação **não pode** ser nem A nem B. O pedido do Leo foi literal: *"estilo bem diferente"*.
Uma terceira proposta que seja "A com outro tom de bronze" é uma entrega falhada.

**Você escolhe a direção.** Escolha uma, declare-a **em uma frase no topo da página**, e
**comprometa-se inteiramente** com ela — meia ruptura fica pior que nenhuma. Direções possíveis,
para calibrar a ambição (você pode propor outra):

- **Jogo / console** — o app já tem pontos, nível, ciclo, saldo, semana 4/12. Hoje isso vive
  escondido numa aba de Revisão. E se o placar fosse o app? Números enormes, cor saturada, botões
  com peso físico, recompensa audível-visível. Serve diretamente ao procrastinador.
- **Terminal / brutalista** — mono em tudo, grade visível, zero cantos arredondados, densidade
  alta, hierarquia por peso e caixa. Serve diretamente ao detalhista, e é rápido de ler.
- **Tátil / objeto físico** — cartões com espessura, o rito como um interruptor que se puxa, o dia
  que se fecha como uma gaveta. A recompensa é o gesto, não o selo.
- **Uma tela, uma pergunta** — o oposto de tudo: nada de listas, nada de abas. O app pergunta uma
  coisa por vez, em tela cheia, e você desliza. Menos escolha é menos fricção.

Regras da ruptura:

- **Proponha seus próprios tokens.** Você não está preso a `#DEB878` nem à paleta `light`. Se
  mudar a paleta inteira, mude — mas mostre a nova em tabela e defenda cada cor.
- Pode mudar tipografia, densidade, forma, navegação, quantidade de telas, o modelo mental.
- Pode mudar a arquitetura de informação: se sua direção implica jogar fora a tabbar de 4, jogue.

## Onde a ruptura NÃO pode chegar

Três coisas não se negociam, porque não são estilo — são o problema:

1. **Os seis princípios do briefing original.** Um toque resolve; escrever nunca bloqueia; um
   primário por tela; a tela diz o que precisa dele; fechar devolve; sistema, não telas. Uma
   proposta linda que aumente a energia de ativação está errada, por mais original que seja.
2. **Os dados são reais.** Rótulos, campos, estados, endpoints e nomes de arquivo vêm do código
   que você vai ler. Nada de app genérico de produtividade.
3. **É implementável no stack real.** React Native + Expo 54, ícones Feather, `Animated` puro
   (reanimated **não** está instalado), `expo-linear-gradient` disponível, componentes caseiros em
   `app/src/ui.tsx`. Se sua direção exigir algo fora disso, diga o custo explicitamente na seção de
   ondas em vez de fingir que é de graça.

E uma honestidade obrigatória: a página deve ter uma seção curta **"o que esta variação sacrifica"**.
Toda ruptura troca algo por algo. Nomeie o que se perde em relação a A.

## Entregáveis (nomes exatos)

- `design/proposta-visual-kimi-radical.html`
- `design/NOTAS-KIMI-RADICAL.md`

## Restrições duras

- Repositório **inteiro somente leitura**, exceto `projects/escritorio/design/`.
- **Não delegue para subagentes.** O processo termina quando você devolve o turno; qualquer
  trabalho em background é perdido. Faça tudo você mesmo e só devolva o turno depois de os dois
  arquivos estarem escritos em disco.
- Nada de `git`, `npm`, `expo`, testes ou instalação.
- Não faça perguntas: decida e justifique dentro do próprio HTML.
