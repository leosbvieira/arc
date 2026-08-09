# Briefing B — variação CLARA

Leia primeiro `BRIEFING.md` (nesta mesma pasta). **Tudo o que está lá continua valendo**: quem é
o Leo, os princípios que decorrem de "detalhista + procrastinador", o stack real, os problemas
conhecidos, a estrutura do documento (princípios → mockups → antes/depois → sistema → ondas) e as
telas obrigatórias (Fechar o dia, Home, substituto de "Ferramentas", Abertura, Captura).

Este arquivo só diz **o que muda** nesta variação.

## Já existe uma variação A

`proposta-visual-kimi.html` (você mesmo fez) é a **variação A**: escura, "midnight desk", premium
mono, sóbria — bronze `#DEB878` sobre `#080A0D`, Fraunces + Space Grotesk + IBM Plex Mono, muito
respeito à base existente.

Ela foi **aprovada**. Esta variação B não substitui: é uma alternativa a ser comparada lado a lado.
Não copie o CSS dela e não repita as mesmas soluções visuais. Mantenha só a **estrutura do
documento** e os **fatos do código**, para que a comparação seja justa.

## O que muda: claro, e outro estilo

**1. Tema claro.** O `theme.ts` já tem uma paleta `light` pronta e nunca usada:
`bg #FAFAF9`, `bgRaised #F2F0EC`, `surface/card #FFFFFF`, `card2 #F4F4F5`,
`border rgba(0,0,0,0.09)`, `text #18181B`, `textMuted #71717A`, **`primary #A9834F`**,
`danger #C56A5A`, `success #4E9A72`, `info #557DB7`, `lilac #8172AA`.
Use-a como ponto de partida real (o comentário no código diz que o light "fica pronto pro toggle").
Você pode ajustar/estender, mas justifique cada desvio.

Tanto os **mockups** quanto a **página da proposta** ficam claros. Nada de página escura com
telas claras dentro.

**2. Outro estilo, não a variação A pintada de branco.** Este é o ponto que separa entrega boa de
entrega preguiçosa. A direção desta variação é **editorial / papel**:

- Espaço em branco generoso; a calma vem do respiro, não da escuridão.
- Hierarquia por **tipografia e régua**, não por cartão escuro sobre fundo escuro. Menos caixas:
  linhas finas, agrupamento por espaço, cartão só quando for realmente um objeto.
- Serifa com papel protagonista — títulos maiores e mais confiantes que em A.
- Sombra quase inexistente; profundidade por contraste e borda de 1px.
- O accent `#A9834F` é **raro e caro**: aparece no primário e em quase nada mais. Num fundo claro,
  cor demais vira ruído — e ruído, para este usuário, vira adiamento.

Um contraponto deliberado: se A era um escritório à meia-noite, B é a **mesa de manhã, papel bom,
luz de janela**. O app é usado nos dois momentos do dia; faz sentido que exista uma proposta para
cada um.

**3. Ganho próprio, não só paridade.** Um tema claro muda o que é fácil e o que é difícil:
- Estados de conclusão e recompensa (`RewardSeal`) precisam de outra solução — glow bronze sobre
  preto não existe aqui. Resolva de verdade, não copie.
- Legibilidade sob sol e à noite: diga em uma linha, na própria página, quando cada tema serve.
- Alvos de toque grandes continuam obrigatórios (56px nos ritos, 44px mínimo).

**4. Acessibilidade como argumento visível.** No fundo claro, contraste é fácil de errar. Garanta
texto normal ≥ 4.5:1 e mostre isso na seção de tokens — o Leo é detalhista e vai conferir.

## Entregáveis (nomes exatos)

- `design/proposta-visual-kimi-clara.html`
- `design/NOTAS-KIMI-CLARA.md`

## Restrições duras (idênticas ao briefing original)

- Repositório **inteiro somente leitura**, exceto `projects/escritorio/design/`.
- **Não delegue para subagentes.** O processo termina quando você devolve o turno; qualquer
  trabalho em background é perdido. Faça tudo você mesmo e só devolva o turno depois de os dois
  arquivos estarem escritos em disco.
- Nada de `git`, `npm`, `expo`, testes ou instalação.
- Não faça perguntas: decida e justifique dentro do próprio HTML.
