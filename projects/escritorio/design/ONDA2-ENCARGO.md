# Encargo — Onda 2: a voz nova (Bricolage Grotesque + Syne)

Onda 1 está entregue e verificada. Esta é a **onda 2** da `proposta-c2-sobria.html` aprovada:
trocar as famílias de fonte do app inteiro. Sem lógica nova, sem tela nova, sem backend.

O plano da proposta chama isto de "1 dia · mecânico". **Não é.** A revisão levantou os 42 sítios de
`fonts.serif` e eles não vão todos para o mesmo lugar: alguns viram Syne, a maioria vira Bricolage,
um vira mono. Trocar os 42 em bloco reintroduz exatamente a textura que o Leo rejeitou na variação
C. A tabela da seção 4 já resolve isso — **siga a tabela, não o achismo**.

---

## 0. Autoridade — quando o mockup se contradiz

A seção 02 da proposta diz que a Syne aparece "uma, no máximo duas" vezes por tela. Os **frames
desenhados** da mesma proposta usam Syne seis vezes na Home (saudação, nível, título do hero, três
valores de stat). É contradição interna do documento.

**A regra é: o frame desenhado vence a prosa.** O Leo aprovou olhando as telas, não lendo o texto.
A prosa só decide onde não há frame — e ali ela é dura: **Syne nunca em corpo de texto, label,
botão, item de lista ou eyebrow.**

---

## 1. Pacotes — o único passo que precisa de rede

```
npx expo install @expo-google-fonts/bricolage-grotesque @expo-google-fonts/syne
```

Este é o **único** comando de instalação autorizado. Nada de `npm update`, `npm audit fix`, nada de
apagar `node_modules`, nada de mexer em outra dependência — há outra sessão trabalhando no mesmo
repositório e o lockfile é compartilhado.

**Fraunces e Space Grotesk continuam instalados.** A proposta manda removê-los; não removemos agora,
de propósito: se a dupla Bricolage+Syne brigar no aparelho, a saída descrita na própria proposta
(Bricolage 700 cobrindo os dois papéis) e o retorno ao estado atual passam a ser edição de 3 linhas
no `theme.ts` em vez de reinstalação. Peso morto em `node_modules` não custa nada em runtime — o
Metro só empacota o `.ttf` que o `useFonts` referencia. A limpeza é da onda 3.

**Depois de instalar, confira os nomes reais dos exports** em
`node_modules/@expo-google-fonts/bricolage-grotesque/index.js` e `.../syne/index.js`. A convenção
do gerador do Expo é `<FamíliaPascal>_<peso><Estilo>` (o `space-grotesk` já instalado exporta
`SpaceGrotesk_500Medium` assim), então o esperado é:

- `BricolageGrotesque_400Regular` · `_500Medium` · `_600SemiBold` · `_700Bold`
- `Syne_600SemiBold` · `Syne_700Bold`

Se algum nome divergir, **use o nome real** e diga na resposta. Bricolage Grotesque é fonte variável
no Google Fonts (eixos `opsz`/`wdth`/`wght`); o pacote do Expo publica instâncias estáticas, e é só
delas que o app se serve — não tente acessar eixo variável, não existe API para isso aqui.

---

## 2. `app/App.tsx` — o `useFonts`

Saem: `Fraunces_500Medium` e os quatro `SpaceGrotesk_*`.
Entram: os quatro `BricolageGrotesque_*` e **dois** `Syne_*` (600 e 700).
Permanece: `IBMPlexMono_500Medium`.

`Syne_800ExtraBold` **não é carregada.** Ela existe no espécime só como demonstração do que se
evita — carregar um arquivo que ninguém usa é peso puro.

Os imports no topo do arquivo mudam junto (`@expo-google-fonts/fraunces` e
`@expo-google-fonts/space-grotesk` saem das linhas de import).

---

## 3. `app/src/theme.ts` — o mapa `fonts`

```ts
export const fonts = {
  ui: "BricolageGrotesque_400Regular",
  uiMedium: "BricolageGrotesque_500Medium",
  uiSemi: "BricolageGrotesque_600SemiBold",
  uiBold: "BricolageGrotesque_700Bold",
  display: "Syne_600SemiBold",
  displayBold: "Syne_700Bold",
  mono: "IBMPlexMono_500Medium",
};
```

Duas decisões aqui, e as duas são de propósito:

1. **`serif` some do mapa.** Não deixe alias de compatibilidade. `fonts` é objeto simples, então
   qualquer `fonts.serif` que sobrar vira **erro de compilação** — é assim que o `npm run typecheck`
   vira a prova de que nenhum dos 42 sítios ficou para trás. Alias silencioso mataria essa garantia.
2. **`ui` passa a ser 400, e entra `uiMedium` (500).** Hoje `ui` é `SpaceGrotesk_500Medium`. A
   proposta pede Bricolage 400/500 no corpo, com 500 carregando listas. Para **não** virar uma
   segunda varredura de centenas de sítios: `uiMedium` existe para quem precisar, mas **não saia
   trocando `fonts.ui` por `fonts.uiMedium` em lugar nenhum**. Se o corpo em 400 ficar leve demais no
   aparelho, a correção é uma linha (`ui: "...500Medium"`), depois que o Leo vir.

Paleta `dark`/`light`, `POINTS`, `AREA_COLORS`, `spacing`, `radius`, `shadow`: **intactos**.

---

## 4. Os 42 sítios de `fonts.serif` — a tabela

Cada linha é um `fontFamily: fonts.serif` real no código. Troque **só o `fontFamily`**.
Cor, tamanho e `lineHeight` ficam como estão (as exceções de `letterSpacing` estão na seção 5).

### → `fonts.display` (Syne 600) — título de tela, saudação, herói, valor de stat

| arquivo:linha | estilo | por quê |
|---|---|---|
| `App.tsx:424` | `section` | título da tela no header — é o `.scr-title` do mockup |
| `src/screens/Home.tsx:311` | `greeting` | "o momento Syne da tela", dito com todas as letras nas notas do frame |
| `src/screens/Home.tsx:315` | `levelNumber` | o "4" do selo: o mockup desenha display 18px |
| `src/screens/Home.tsx:321` | `heroTitle` | `.hq-title` do mockup é display |
| `src/screens/Home.tsx:329` | `metricValue` | `.s-value` do mockup é display |
| `src/screens/Abertura.tsx:780` | `toqueTitulo` | herói centralizado da tela do toque |
| `src/screens/Agenda.tsx:158` | `titulo` | título de tela |
| `src/screens/Capture.tsx:1797` | `captureTitle` | título de tela |
| `src/screens/Capture.tsx:1830` | `readingTitle` | título de tela (modo leitura) |
| `src/screens/Chat.tsx:351` | `railBrand` | marca do rail, aparece uma vez |
| `src/screens/Chat.tsx:367` | `emptyChatTitle` | herói do estado vazio, sozinho na tela |
| `src/screens/Habitos.tsx:362` | `title` | título de tela |
| `src/screens/Habitos.tsx:367` | `scoreValue` | valor de stat |
| `src/screens/Revisao.tsx:883` | `nivel` | número-herói do card de conquistas |
| `src/screens/Revisao.tsx:934` | `reviewPct` | número-herói |
| `src/screens/Revisao.tsx:935` | `monthPct` | número-herói |
| `src/screens/Tasks.tsx:442` | `signalNumber` | valor de stat |
| `src/screens/Triagem.tsx:214` | `summaryCount` | valor de stat |

### → `fonts.displayBold` (Syne 700) — só número que chega pronto e parado

| arquivo:linha | estilo | por quê |
|---|---|---|
| `src/ui.tsx:613` | `rewardHero` | o "+140" da RewardSheet. O comentário no código já diz: *"display/Syne chega na onda 2"*. **Apague esse comentário** ao cumprir — comentário de dívida paga vira mentira. |

### → `fonts.uiSemi` (Bricolage 600) — título de card, nome, estado vazio

Estes hoje são serif e **repetem dentro da mesma tela**. Em Syne viram a textura rejeitada.

| arquivo:linha | estilo |
|---|---|
| `src/ui.tsx:479` | `sectionTitle` (do `SectionHeader` — ver seção 6b, é o sítio mais delicado) |
| `src/TaskDetailModal.tsx:221` | `name` |
| `src/screens/Capture.tsx:1853` | `bookTitle` |
| `src/screens/Capture.tsx:1869` | `emptyTitle` |
| `src/screens/Habitos.tsx:371` | `sectionTitle` |
| `src/screens/Habitos.tsx:374` | `formTitle` |
| `src/screens/Habitos.tsx:398` | `emptyTitle` |
| `src/screens/Rotinas.tsx:634` | `emptyTitle` |
| `src/screens/Rotinas.tsx:645` | `editorTitle` |
| `src/screens/Settings.tsx:113` | `title` |
| `src/screens/Revisao.tsx:860` | `title` |
| `src/screens/Revisao.tsx:933` | `reviewTitle` |
| `src/screens/Tasks.tsx:412` | `createTitle` |
| `src/screens/Tasks.tsx:481` | `emptyTitle` |
| `src/screens/Triagem.tsx:228` | `emptyTitle` |

### → `fonts.ui` (Bricolage 400) — prosa

Texto corrido de 15–18px. É o proibido explícito da seção 02: Syne em corpo vira textura.

| arquivo:linha | estilo |
|---|---|
| `App.tsx:412` | `tagline` |
| `src/screens/Abertura.tsx:927` | `prioridade1` |
| `src/screens/Chat.tsx:384` | `soul` |
| `src/screens/Chat.tsx:387` | `groundV` |
| `src/screens/Edificacao.tsx:221` | `lead` |
| `src/screens/Melhorias.tsx:367` | `lead` |
| `src/screens/Triagem.tsx:211` | `lead` |

### → `fonts.mono` — número que precisa alinhar em coluna

| arquivo:linha | estilo | por quê |
|---|---|---|
| `src/screens/Agenda.tsx:156` | `diaNumero` | são **sete** chips de dia lado a lado. Syne é expandida e não tem figuras tabulares: cada chip ficaria com largura diferente e a fita de dias desalinha. O rótulo acima dele (`diaRotulo`) já é mono. |

**Conferência:** 18 + 1 + 15 + 7 + 1 = **42**. Se o seu `grep` achar um sítio fora desta lista, ele
foi criado pela outra sessão depois deste levantamento — classifique pela regra da seção 5 e
**diga na resposta**. Não invente entrada nova em silêncio.

---

## 5. `letterSpacing` — o único número que muda junto

Fraunces é estreita e pedia tracking negativo forte. **Syne é expandida e não pede.** O mockup usa
cerca de −0.012em: 25px → −0.3 · 22px → −0.2 · 19px → −0.2.

Nos sítios que viraram `display`/`displayBold`, **reduza o `letterSpacing` negativo pela metade**,
arredondando para 0.05. Exemplos concretos: `Home.greeting` −0.7 → **−0.35**; `Home.heroTitle` −0.6
→ **−0.3**; `App.section` −0.35 → **−0.2**; `Capture.captureTitle` −0.7 → **−0.35**;
`ui.rewardHero` −1 → **−0.5**. Onde não há `letterSpacing`, não adicione.

Nos sítios que viraram `ui`/`uiSemi`/`mono`: **não mexa no `letterSpacing`.**

**Não retune `fontSize` nem `lineHeight` em lugar nenhum.** Bricolage tem altura-x um pouco maior
que Space Grotesk; a diferença é visual, e quem decide é o Leo vendo no aparelho. Só mexa se houver
**clipping real** — e se mexer, liste o quê e por quê.

---

## 6. Riscos conhecidos — leia antes, não depois

**a) Syne é larga. A onda 1 já sangrou por largura.** O defeito nº 1 da onda 1 foi um rótulo
estourando a linha porque no Yoga o `flexShrink` padrão é **0**, não 1 como no CSS. Trocar por uma
fonte expandida é exatamente o mesmo risco de novo.

O sítio mais exposto é o `App.tsx:424 section`: ele fica numa `row` entre dois blocos de **72px
fixos** (`brandSmall` e o espaçador), e o título mais longo é "Hábitos a reduzir". Em Syne 600 20px
isso não cabe num aparelho de 360dp.

→ **Onde um `display` vive dentro de uma `row`, garanta `flexShrink: 1` no estilo e
`numberOfLines={1}` no `<Text>`.** Comece pelo `App.tsx`. Verifique também `Home.heroTitle`
(tem `maxWidth: "82%"`, provavelmente já resolve) e os `metricValue` das três colunas de stat.

**b) `ui.tsx:479 sectionTitle` é o sítio mais delicado do encargo.** O `SectionHeader` repete 4×
numa Home só. No mockup, cabeçalho de seção repetido **não é display** — virou eyebrow mono em caixa
alta ("EM ESPERA", "AGENDA CURTA"). Mas isso é mudança de *estrutura*, e a Home é reconstruída na
onda 3. Nesta onda ele vai para `uiSemi`: fica quieto, sai do caminho da Syne, e a onda 3 decide o
formato final. **Não antecipe a onda 3** transformando o SectionHeader em eyebrow agora.

**c) Não toque em nada que não seja `fontFamily`/`letterSpacing`.** Em particular: **nenhuma cor**.
`Revisao.reviewPct` é bronze e continua bronze — a disciplina de "um bronze cheio por tela" é da
onda 4, junto com o Placar. Misturar aqui torna a revisão impossível.

---

## 7. Não regrida a onda 1

`src/ui.tsx` e `src/screens/Fechar.tsx` acabaram de ser consertados. Preserve:

- `BigAction`: o `flexShrink: 1` do sub e o `numberOfLines={1}` — **não remova**;
- `Fechar.tsx`: a constante única `temTexto` e o comentário que explica por que ela é única;
- `closingPoints.ts` e `tests/closingPoints.test.mjs`: **não abra**. Não têm fonte nenhuma.

Se um comentário existente explica um bug, mantenha o comentário.

---

## 8. Verificação (obrigatória antes de devolver o turno)

De dentro de `projects/escritorio/app`:

```
npm run typecheck
npm test
```

`typecheck` limpo é a **prova de completude** desta onda: `serif` não existe mais no mapa, então
qualquer sítio esquecido aparece como erro. Os 71 testes têm que continuar passando (eles não tocam
em fonte — se algum quebrar, você mexeu em algo fora do escopo).

Cole a **saída real** dos dois na resposta.

---

## 9. Restrições

- Arquivos permitidos: `app/package.json` e `app/package-lock.json` (só pelo `expo install` da
  seção 1), `app/App.tsx`, `app/src/theme.ts`, e os 16 arquivos listados na tabela da seção 4.
- **Nada em `bff/`.** Nada em `Melhorias.tsx`, `melhoriasView.ts`, `api.ts`, `Revisao.tsx` **além
  das trocas de `fontFamily` listadas** — há outra sessão editando esses arquivos.
- **Nada de `git`** (nem `add`, nem `commit`, nem `checkout`, nem `stash`).
- **Não delegue para subagentes**: no modo `-p` o processo morre quando você devolve o turno. Só
  devolva o turno depois de os arquivos estarem escritos.
- Não faça perguntas: decida e siga, e explique as decisões na resposta final.

Na resposta final, liste: os nomes reais dos exports das duas fontes, os arquivos tocados, qualquer
sítio onde você divergiu da tabela e por quê, os lugares onde precisou de `flexShrink`/
`numberOfLines`, e a saída real de `npm run typecheck` e `npm test`.
