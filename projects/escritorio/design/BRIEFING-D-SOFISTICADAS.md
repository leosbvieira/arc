# Briefing D — três versões sofisticadas (escuro + jogo, sem neon)

Leia primeiro `BRIEFING.md` (mesma pasta). Continuam valendo: quem é o Leo, os seis princípios,
o stack real, os problemas conhecidos, a estrutura do documento e a exigência de dados reais.

Este arquivo descreve **três direções (D1, D2, D3)**. Cada execução faz **uma** delas.

---

## O veredito do Leo sobre A e C

Ele viu a variação **A** (`proposta-visual-kimi.html` — escura, midnight desk, sóbria, Fraunces +
bronze) e a variação **C** (`proposta-visual-kimi-radical.html` — HUD de jogo, verde-elétrico).

**O que ele quer manter:**
- O **escuro**. Não há versão clara aqui.
- A **gamificação da C** — mas dentro do corpo da A.
- **Pontuação visível em cada tarefa.** Não escondida no placar: o valor aparece na linha da tarefa.
- **Streak no fechamento do dia.** A sequência de dias é parte da recompensa de fechar.
- **O placar da C**, que ele achou melhor que o da A.
- A **tipografia da C** é melhor que a da A — *"mesmo assim não é muito boa"*.

**O que ele rejeitou:**
- O **verde-elétrico saturado** e os "detalhes chamativos" da C.
- Palavra dele: quer algo **mais sofisticado**.

---

## O mandato comum às três

**1. Sofisticação é restrição.** A energia do jogo tem que vir de **material, precisão e
hierarquia** — não de saturação. Proibido em todas as três: neon, verde/rosa elétrico,
preenchimentos saturados de área grande, glow difuso, confete, emoji de troféu, badge gigante,
ponto de exclamação, forma de fliperama. Se um elemento chama atenção, que seja por ser o único
elemento brilhante da tela — nunca por gritar.

**2. A base escura permanece.** Fundo `#080A0D`, `bgRaised #0C0F13`, `surface #0E1116`,
`card #15191F`, `card2 #11151A`, borda `rgba(235,222,202,0.11)`, texto `#F4EFE7`,
apagado `#9A9BA3`. As 10 `AREA_COLORS` ficam. **O accent é onde cada direção pode divergir** —
mas justifique, e no máximo dois tons de accent por direção.

**3. Tipografia é entregável de primeira classe.** Ele reclamou dela nas duas versões. Cada direção
propõe um **par (ou trio) tipográfico próprio**, e a página precisa de uma seção
**"Espécime"** mostrando, em tamanho real:
- a escala de títulos, corpo e eyebrow;
- **os algarismos grandes do placar** (é o que ele mais vai olhar), com **figuras tabulares**
  para os números não dançarem ao atualizar;
- o mesmo número em dois pesos, para provar a escolha.

Restrição de implementação: **só fontes disponíveis no Google Fonts**, porque o app usa
`@expo-google-fonts` (hoje carrega Fraunces, Space Grotesk e IBM Plex Mono). Sugestões por direção
abaixo; pode trocar, mas diga por quê e confirme que existe no Google Fonts.

**4. As três exigências novas do Leo, em toda direção:**

- **Pontos por tarefa.** Cada linha de tarefa mostra o que ela vale. Desenhe a coisa toda: como o
  valor aparece sem virar ruído em uma lista de 12 tarefas, o que acontece no toque de concluir
  (o número sai da linha e vai para o saldo?), e como o total do dia se forma.
- **Streak no fechamento.** A tela de recompensa do `Fechar.tsx` mostra a sequência de dias.
  Resolva o caso difícil também: **como a quebra da sequência é comunicada sem punir** — o código
  tem a regra "placar informa, não julga; pontos nunca descem", e ela vale.
- **Placar melhor.** Herde a ambição da C (saldo, nível, ciclo, semana, ganho/desconto — tudo já
  existe em `Revisao.tsx`), com o acabamento da A.

**5. Honestidade sobre dados.** Dois pontos já levantados e não resolvidos, que cada direção deve
tratar explicitamente no plano de ondas:
- não existe tabela de **pontos por tipo de ação** no app — proposta anterior foi uma tabela local
  em `theme.ts` até o BFF expor;
- o **streak corrido** provavelmente exige campo novo no BFF (`semanal.dailies` dá a base).
Diga o custo, não finja que é de graça.

**6. Uma seção obrigatória: "o que herdei de A e de C, e o que rejeitei"** — em quatro ou cinco
linhas, sem diplomacia.

---

## Telas obrigatórias (as cinco que importam para este pedido)

1. **Fechar o dia** — o rito (um toque) **e** a recompensa com streak. Dois frames.
2. **Tarefas** — com pontuação por linha, e o gesto de concluir.
3. **Placar** (a tela de Revisão) — o herói desta rodada.
4. **Home / Hoje** — como o jogo aparece sem virar cassino.
5. **O substituto de "Ferramentas"** — navegação com sinal.

Abertura e Captura são bem-vindas se couberem, mas não custe as cinco acima por elas.

---

## As três direções

### D1 — "Cofre": metal, gravação, medalha

A energia vem de **material nobre**, não de cor. O accent é o bronze que já existe, e o jogo é
expresso por **valor e relevo**: número gravado, borda dupla, bisel de 1px, medalha em baixo-relevo,
folha metálica. Nada de segunda cor saturada — se precisar de contraste, use um **segundo metal**
(champanhe/platina dessaturado), nunca um segundo hue vibrante. O placar parece o interior de um
cofre pessoal; o streak, uma fileira de marcas cinzeladas.

Tipografia sugerida (Google Fonts): **Archivo** ou **Archivo Expanded** para os algarismos grandes
(largura e peso sem gritaria), **Inter** ou **Instrument Sans** para UI, mono técnico para eyebrows.
Sem serifa — ou serifa só se defender bem.

### D2 — "Instrumento": painel de precisão

A energia vem de **medição**. Escala com traços, agulhas finas, réguas, leituras. O accent quente
recua e vira **frio e discreto** (aço, gelo, um azul-petróleo dessaturado), com o bronze rebaixado a
detalhe raro. Nada preenche área grande: tudo é fio de 1px, tick e algarismo. O placar é um
mostrador; o streak, uma fita de registro contínuo (tipo sismógrafo/strip chart) — que resolve
elegantemente a quebra: o traço fica, o vazio é visível, ninguém é punido.

Tipografia sugerida: mono de verdade com figuras tabulares — **JetBrains Mono**, **Martian Mono** ou
**IBM Plex Mono** — como protagonista dos números, e **Inter Tight** / **Instrument Sans** para o
texto. Zero serifa.

### D3 — "Noturno editorial": a alma da A, com tipografia melhor

A mais próxima da A, e por isso a que precisa provar a evolução na **tipografia** e no **jogo**.
Mantém a sobriedade editorial, mas **troca Fraunces** por uma serifa mais afiada e moderna
(**Instrument Serif**, **Newsreader** ou **Fraunces com eixo óptico ajustado** — decida e defenda), e
faz os números do placar virarem **peça tipográfica**: algarismo enorme, fios de cabelo, muito
respiro. O jogo aparece como **notação**, não como HUD: o ponto ganho é um número elegante ao lado
da tarefa, o streak é uma linha de dias com o tipo carregando o peso. Accent bronze mantido e
raro.

---

## Entregáveis por direção (nomes exatos)

| direção | HTML | notas |
|---|---|---|
| D1 | `design/proposta-d1-cofre.html` | `design/NOTAS-D1.md` |
| D2 | `design/proposta-d2-instrumento.html` | `design/NOTAS-D2.md` |
| D3 | `design/proposta-d3-editorial.html` | `design/NOTAS-D3.md` |

Estrutura do documento igual às anteriores: princípios (curtos — os seis já existem, não repita a
íntegra) → **espécime tipográfico** → mockups → antes/depois onde ajudar → sistema (tokens +
componentes renderizados) → herança/rejeição → plano em ondas com nome de arquivo real.

---

## Restrições duras

- Repositório **inteiro somente leitura**, exceto `projects/escritorio/design/`.
- **Não delegue para subagentes.** No modo `-p` o processo morre quando você devolve o turno;
  trabalho em background é perdido. Faça tudo você mesmo e só devolva o turno depois de os dois
  arquivos estarem escritos em disco.
- Nada de `git`, `npm`, `expo`, testes ou instalação.
- Não faça perguntas: decida e justifique dentro do próprio HTML.
- Implementável no stack real: React Native + Expo 54, ícones Feather, `Animated` puro
  (**reanimated não está instalado**), `expo-linear-gradient` disponível, componentes caseiros em
  `app/src/ui.tsx`.
