# Briefing C2 — a variação C, sóbria e com a tipografia decidida

Leia `BRIEFING.md` (contexto do app, os seis princípios, stack real, problemas conhecidos) e
`proposta-visual-kimi-radical.html` (a variação **C**, que é a base aprovada).

O Leo escolheu a **C como base**. Esta rodada é a C corrigida, não uma variação nova.

---

## O que ele aprovou na C

- O escuro.
- A gamificação: o placar como peça central, pontos visíveis, recompensa imediata.
- **Pontuação em cada tarefa** — ele confirmou que quer, **mas discreta**. Nas versões D isso virou
  poluição e ele reclamou explicitamente ("não gostei do menu de pontuação").
- **Streak no fechamento do dia.**
- O placar da C é melhor que o da A.

## O que ele rejeitou

- **O verde-elétrico saturado.** Sai.
- Os "detalhes chamativos". A palavra dele, repetida em três rodadas: quer **sofisticado**.

---

## 1. Tipografia — já decidida pelo Leo, não reabra

Ele escolheu, contra a recomendação do espécime e sabendo disso: **Bricolage Grotesque + Syne**.

Sua tarefa é fazer essa escolha **funcionar bem**, não questioná-la. Três obrigações:

- **Atribua papéis distintos.** As duas são famílias de personalidade forte; se disputarem o mesmo
  espaço, o resultado é barulho — exatamente o que ele rejeita. Decida quem é voz (títulos,
  saudação, algarismo-herói) e quem é UI/estrutura, e defenda a divisão. Considere que Syne é
  expandida de mostrador (boa em número grande e título curto) e Bricolage é grotesca com caráter.
- **Uma mono permanece para número vivo.** Nem Bricolage nem Syne têm figuras tabulares, e
  `font-variant-numeric` não é confiável no React Native (o Android não garante). Portanto:
  todo número que **atualiza ao vivo** (saldo contando, total do dia somando) e todo número
  **miúdo em lista** (o `+10` da tarefa) sai em **IBM Plex Mono**, que o app já carrega e é tabular
  por desenho. Número que **chega pronto** (a recompensa `+140`, o saldo-herói) pode ser Syne.
- **Domar o caráter.** Ambas ficam chamativas se usadas grandes, em caixa alta e com peso alto ao
  mesmo tempo. Escolha **no máximo uma** dessas três alavancas por elemento. Mostre no espécime da
  página o mesmo título em duas configurações, provando a contenção.

Confirme os pacotes `@expo-google-fonts` das três famílias e o custo em `theme.ts` e `App.tsx`.

**Se você concluir que as duas juntas realmente brigam**, entregue mesmo assim a versão com as duas
(é a escolha dele) e acrescente, na mesma página, um bloco curto mostrando a alternativa de
**uma só delas + mono** — com o argumento em duas linhas. Ele decide vendo, não lendo.

## 2. Cor — a correção principal

O verde-elétrico sai. Escolha uma estratégia de accent **sóbria** e defenda-a com uma pequena
comparação de amostras na página. Regras:

- Base escura mantida: `#080A0D`, `bgRaised #0C0F13`, `surface #0E1116`, `card #15191F`,
  `card2 #11151A`, borda `rgba(235,222,202,0.11)`, texto `#F4EFE7`, apagado `#9A9BA3`.
  As 10 `AREA_COLORS` ficam.
- **No máximo dois tons de accent.** Proibidos: neon, saturado em área grande, glow difuso,
  confete, badge gigante, forma de fliperama.
- O bronze `#DEB878` do app está disponível, mas note o argumento levantado na rodada anterior:
  *bronze quente em todo botão e todo selo era, ele mesmo, o chamativo*. Se mantiver o bronze,
  torne-o **raro**. Se trocar, justifique.

## 3. Pontuação discreta — o ponto que já falhou uma vez

Ele quer o valor na linha da tarefa **e** reclamou de poluição. Então resolva de fato:

- O `+10` deve ler como **metadado**, não como recompensa: mono miúda, tom apagado, coluna de
  margem alinhada, sem pill, sem fundo, sem cor de destaque enquanto a tarefa está aberta.
- O momento em que ele **vira** recompensa é o toque de concluir — aí sim ganha cor e movimento,
  por menos de 400ms.
- Mostre a lista com **12 tarefas** no mockup, não com 3. O teste da discrição é a lista cheia:
  se a coluna de pontos criar textura visual, está errado.

## 4. Streak no fechamento

Na tela de recompensa do `Fechar.tsx`. Mostre a sequência atual e o recorde, e resolva a **quebra
sem punir** — o código tem a lei "placar informa, não julga; pontos nunca descem". Sem vermelho,
sem texto de culpa.

## 5. Honestidade de dados (não é de graça)

- **Pontos por tipo de ação não existem** no app nem no BFF. Proposta anterior: tabela local
  `POINTS` em `theme.ts`, provisória, display-only — o saldo oficial de `getPontos()` sempre vence.
- **Streak corrido exige campo novo no BFF** (`semanal.dailies` dá só a base).
Declare os dois no plano de ondas com custo, e garanta que as primeiras ondas **não** dependam de
backend.

---

## Telas obrigatórias

1. **Fechar o dia** — o rito (um toque) **e** a recompensa com streak. Dois frames.
2. **Tarefas** — lista cheia (12 itens), pontuação discreta, e o gesto de concluir.
3. **Placar** (tela de Revisão) — a peça central desta direção.
4. **Home / Hoje**.
5. **O substituto de "Ferramentas"**.

## Entregáveis (nomes exatos)

- `design/proposta-c2-sobria.html`
- `design/NOTAS-C2.md`

Estrutura: o que mudou em relação à C (curto e direto) → espécime tipográfico com as escolhas →
mockups → sistema (tokens + componentes renderizados) → plano em ondas com nome de arquivo real.

## Restrições duras

- Repositório **inteiro somente leitura**, exceto `projects/escritorio/design/`.
- **Não delegue para subagentes**: no modo `-p` o processo morre quando você devolve o turno.
  Faça tudo você mesmo e só devolva o turno depois de os dois arquivos estarem escritos em disco.
- Nada de `git`, `npm`, `expo`, testes ou instalação.
- Não faça perguntas: decida e justifique na própria página.
- Implementável no stack real: Expo 54, ícones Feather, `Animated` puro (**sem reanimated**),
  `expo-linear-gradient` disponível, componentes caseiros em `app/src/ui.tsx`.
