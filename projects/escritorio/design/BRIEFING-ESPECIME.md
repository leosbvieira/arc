# Briefing — espécime tipográfico (só tipografia, nenhuma tela)

Contexto rápido: o app é o Aeternum ("escritório"), centro de comando pessoal do Leo, React Native
+ Expo 54, tema **escuro**. Já existem cinco propostas visuais nesta pasta. O Leo escolheu a
direção **C** (`proposta-visual-kimi-radical.html`, HUD de jogo) como base — mas a tipografia
segue sem resolver. Palavras dele sobre a variação C: *"a fonte é melhor, mesmo assim não é muito
boa"*. Sobre a variação A (Fraunces + Space Grotesk + IBM Plex Mono): pior ainda.

**Esta tarefa não redesenha tela nenhuma.** O entregável é uma página para ele escolher a
tipografia olhando, comparando e decidindo. Nada de mockup de celular, nada de plano de ondas.

---

## O diagnóstico que já temos

A variação D3 investigou e concluiu (verifique se concorda, e diga se discorda):

> Fraunces é fonte de eixo óptico — brilha a 60px+ com `opsz` alto e os eixos SOFT/WONK. O app
> carrega uma instância **estática** (`Fraunces_500Medium`) e a usa a **18–34px**, onde ela
> engrossa e fica "fofa". Ajustar o eixo no stack real não existe: `@expo-google-fonts` entrega
> instâncias estáticas por peso, sem `opsz`.

Se isso estiver certo, o espécime deve **provar visualmente** o problema, não só afirmá-lo.

## Restrição de implementação (dura)

Só famílias que existam no **Google Fonts** *e* tenham pacote `@expo-google-fonts`. Confirme o nome
do pacote de cada candidata (ex.: `@expo-google-fonts/instrument-serif`). Uma fonte linda que não
carrega no Expo é uma fonte inútil aqui — não inclua.

## O que o app pede da tipografia (é isto que decide a escolha)

O sistema tem **três papéis** distintos, e a escolha é de um **conjunto**, não de uma fonte:

1. **Voz** — saudação ("Boa noite, Leo."), títulos de tela e de seção. Tamanhos reais: 21, 27, 30.
2. **UI** — rótulos, corpo, botões, metadados. Tamanhos reais: 11.5, 12.5, 13.5, 14.5, 16.
3. **Número** — e aqui está o ponto crítico desta rodada, porque a base C é um placar:
   - **algarismo-herói**: saldo (`1.240`), recompensa (`+140`), nível (`3`) — 40 a 64px;
   - **número que atualiza ao vivo**: saldo contando, total do dia somando. **Precisa de figuras
     tabulares**, senão o dígito dança a cada atualização;
   - **número miúdo em lista**: o valor de pontos na linha de cada tarefa (`+10`), que o Leo quer
     **discreto** — ele reclamou que nas versões D isso virou poluição;
   - **eyebrow** em caixa alta com letter-spacing.

## O que entregar

**Um arquivo**: `design/especime-tipografico.html` — autocontido (CSS inline; `<link>` do Google
Fonts permitido, com fallback declarado), **fundo escuro** (`#080A0D`, cards `#15191F`, texto
`#F4EFE7`), cor quase ausente para que o julgamento seja do tipo e não da paleta.

Conteúdo:

1. **A prova do problema com Fraunces**: a mesma frase em 18 / 24 / 30 / 60px, lado a lado com uma
   alternativa, mostrando onde ela engrossa. Se você discordar do diagnóstico, mostre por quê.

2. **Seis a oito conjuntos candidatos.** Cada conjunto = voz + UI + número, com nome das famílias e
   pacote Expo. Inclua obrigatoriamente **dois controles**, para a comparação ser honesta:
   - o conjunto atual da variação A (Fraunces + Space Grotesk + IBM Plex Mono);
   - o conjunto da variação C (Space Grotesk 700 caixa alta + IBM Plex Mono).

   Cubra famílias de temperamentos diferentes — serifa moderna de alto contraste, grotesca neutra,
   grotesca com caráter, expandida de mostrador, mono de verdade. Curadoria é sua; o critério é
   **sofisticação**, que foi o pedido literal dele (ele rejeitou "chamativo").

3. **Cada conjunto renderizado no MESMO texto e nos MESMOS números**, para comparação justa:
   - `Boa noite, Leo.` (30px) · um título de seção (21px) · uma linha de corpo (13.5px)
   - `ENCERRAR O DIA` como eyebrow mono
   - `1.240` e `+140` em tamanho herói · `nível 3` · `4/6 ritmos` · `sequência 21 dias`
   - uma **linha de tarefa real** com o ponto discreto à direita: `Enviar proposta da Litoral` `+10`
   Fragmentos pequenos em contexto são bem-vindos; **telas inteiras não**.

4. **Prova de figuras tabulares**: mostre o mesmo número mudando (ex.: `1.240` → `1.305` → `1.190`)
   empilhado, para dar para ver se os dígitos ficam na coluna. Marque quais candidatas têm tabular
   por construção (mono) e quais dependem de `font-variant-numeric`, que em React Native **não é
   confiável** — isso pesa na decisão.

5. **Um veredito.** Sua recomendação em primeiro lugar, com o motivo em duas linhas, e uma tabela
   curta "se você quer a sensação X, escolha Y". Ele é detalhista: prefira um argumento verificável
   ("a altura-x maior sustenta 13.5px em tela OLED") a adjetivo.

6. **Custo da troca**: o que muda em `app/src/theme.ts` (objeto `fonts`) e em `App.tsx` (o
   `useFonts`), e quantas famílias o app passa a carregar. Menos famílias é melhor.

Escreva também `design/NOTAS-ESPECIME.md` (máx. 1 página): a recomendação, as descartadas e por quê.

## Restrições duras

- Repositório **inteiro somente leitura**, exceto `projects/escritorio/design/`.
- **Não delegue para subagentes**: no modo `-p` o processo morre quando você devolve o turno e o
  trabalho em background se perde. Faça tudo você mesmo e só devolva o turno depois de os dois
  arquivos estarem escritos em disco.
- Nada de `git`, `npm`, `expo`, testes ou instalação.
- Não faça perguntas: decida e justifique na própria página.
