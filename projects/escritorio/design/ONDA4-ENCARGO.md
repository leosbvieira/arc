# Encargo — Onda 4: o Placar

Última onda da `proposta-c2-sobria.html`. As ondas 1, 2 e 3 estão entregues e revisadas.

A onda 4 do documento tem três linhas. **Duas saem, e o motivo está na seção 9** — leia antes de
achar que faltou coisa. O que fica é a linha principal: *"ConquistasCard vira Placar: saldo-herói
Syne 700 na cor do texto, SegmentBar de ciclo, stats da semana. Desconto permanece em muted (lei
nº 4). Dados 100% existentes."*

Zero endpoint novo. Zero chamada de API nova. Zero dado inventado.

**Não delibere: as decisões estão todas aqui, e a seção 9 fecha as que você poderia querer
reabrir.** Comece pelo item 1 e siga a ordem.

---

## 1. `app/src/format.ts` (novo) + `app/tests/format.test.mjs` (novo) — o teste primeiro

`Revisao.tsx` tem uma função privada `num()` que formata milhar sem depender de `Intl` (o Hermes
não garante `Intl`), com um comentário dizendo exatamente isso. A onda 3a, ao escrever o cartão de
saldo da Home, usou `points.saldo_total.toLocaleString("pt-BR")` — a coisa que `num()` existe para
evitar. Onde o `Intl` não estiver presente, `toLocaleString` **não quebra: ele devolve `"1553"` sem
separador**, calado. O mesmo número apareceria formatado de dois jeitos em duas telas.

Como o Placar promove esse número a herói de 54px, é a hora de resolver.

**Módulo puro, zero `import` de valor** (a convenção do repo: `tsconfig` não tem
`allowImportingTsExtensions`, então o teste `.mjs` importa o `.ts` direto e qualquer `import` de
runtime quebra):

```ts
export function milhar(n: number): string
```

**Comportamento idêntico ao `num()` de hoje, sem "melhorias":**

```ts
return Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
```

O `Math.abs` é deliberado — quem chama escreve o sinal (`−{milhar(semana.desconto)}`), e `desconto`
já chega positivo do BFF. **Não troque por `n.toString()`**: isso mudaria a saída de todos os
chamadores de uma vez.

### O teste, antes do módulo

`app/tests/format.test.mjs`, no padrão `node --test` dos outros: `0` → `"0"`; `999` → `"999"`;
`1000` → `"1.000"`; `1553` → `"1.553"`; `1000000` → `"1.000.000"`; e **`-40` → `"40"`**, com um
comentário dizendo que o valor absoluto é contrato, não descuido — quem chama põe o sinal.
Escreva o teste, rode, veja falhar (módulo inexistente), depois escreva o módulo.

### Os dois chamadores

- `Revisao.tsx`: apague a função `num()` local e o comentário dela, importe `milhar` e troque as
  8 chamadas.
- `Home.tsx`: `points.saldo_total.toLocaleString("pt-BR")` vira `milhar(points.saldo_total)`.
  **É a única linha da Home nesta onda.**

---

## 2. `app/src/screens/Revisao.tsx` — `ConquistasCard` vira `Placar`

Renomeie o componente para `Placar`. Mesma prop (`{ p }: { p: Pontos }`), mesmo ponto de uso, mesmos
três estados de carga (skeleton / cartão / `conqOff`) — **não mexa em nada disso**, é o isolamento
que impede `/pontos` cair e derrubar a Revisão inteira (está comentado no arquivo, linha ~305).

A estrutura nova tem três blocos, nesta ordem:

### 2.1 O herói — fora de qualquer `Card`, no fundo nu

```
              1.380
        PONTOS ACUMULADOS
   N4  ◆◆◆◆  vitalício · não regride
```

- Contêiner: `alignItems: "center"`, `paddingTop: spacing.sm`, `paddingBottom: spacing.lg`.
- **Saldo:** `milhar(p.saldo_total)` em `fonts.displayBold` (Syne 700), `fontSize: 54`,
  `color: colors.text` — **não bronze**, o tamanho já é a ênfase —, `letterSpacing: -1.5`.
  **Não declare `lineHeight`.** O mockup usa `line-height:1`, que em CSS só aperta a caixa; no
  Android um `lineHeight` menor que a altura natural da fonte **corta glifo**. A Syne pede ~1.20 do
  corpo. Deixe o RN calcular.
- **Rótulo:** literal `PONTOS ACUMULADOS`, `fonts.mono`, `fontSize: 9`, `letterSpacing: 2`,
  `color: colors.textMuted`, `marginTop: 8`.
- **Linha do nível:** `flexDirection: "row"`, `justifyContent: "center"`, `alignItems: "center"`,
  `gap: 10`, `marginTop: 13`. Três peças:
  1. `p.nivel > 0 ? \`N${p.nivel}\` : "—"` em `fonts.mono`, `fontSize: 10.5`, `color: colors.text`,
     `letterSpacing: 1`.
  2. `<Diamantes nivel={p.nivel} />` — o componente que já existe. Só o estilo `diamond` muda:
     `width: 8, height: 8, borderRadius: 2` (era 9×9 sem raio). **`borderColor` continua
     `colors.textMuted`** — o mockup usa a cor de linha, mas a 1px ela some e você deixa de
     distinguir N2 de N4. Diamante apagado precisa ser visível para o aceso significar algo.
  3. `p.nivel > 0 ? "vitalício · não regride" : "a caminho do N1"` em `fonts.mono`,
     `fontSize: 8.5`, `color: colors.faint`.

  A linha inteira mede ~199dp num aparelho de 360dp (área útil 328dp). Cabe. Não precisa encolher.

### 2.2 O cartão do ciclo — um `Card`

```
CICLO 3 · SEMANA 4/12              580/800
▬▬▬▬▬▬▬░░░
semana +210      −40 descontos     N4 — topo
─────────────────────────────────────────
padrões (quando houver)
```

- **Linha 1:** `flexDirection: "row"`, `justifyContent: "space-between"`, `alignItems: "baseline"`.
  - esquerda: `CICLO {ciclo.indice} · SEMANA {ciclo.semana}/{ciclo.de}` em `fonts.mono`,
    `fontSize: 9`, `letterSpacing: 1.4`, `color: colors.textMuted`.
  - direita: `{milhar(ciclo.pontos)}/{milhar(ciclo.meta)}` em `fonts.mono`, `fontSize: 10.5`,
    `color: colors.text`.
- **A barra:** `<SegmentBar value={pct} />` dentro de uma `View` com `marginTop: 10`. O `pct` é o
  cálculo que já está no componente. **Deixe os 10 segmentos padrão — não passe `segments={12}`.**
  Ver seção 8, decisão nº 2. Apague `barTrack` e `barFill`.
- **Linha 3:** `flexDirection: "row"`, `justifyContent: "space-between"`, `marginTop: 12`. Três
  `Text`, todos `fonts.mono`, `fontSize: 9.5`, **todos com `flexShrink: 1`**:
  - `semana +{milhar(semana.ganho)}` — `color: colors.success`.
  - `−{milhar(semana.desconto)} descontos` — `color: colors.faint`, **renderizado só quando
    `semana.desconto > 0`** (como hoje). Lei nº 4: desconto nunca em `danger`. O `faint` é um degrau
    abaixo do `muted` e é o token que esta proposta criou justamente para isto.
  - `proximo_nivel ? \`N${n} em ${milhar(faltam)}\` : "N4 — topo"` — `color: colors.textMuted`.
    Isto substitui o bloco `proximo` do rodapé: apague o bloco e o estilo.
- **Padrões:** o bloco `semana.padroes.length > 0` continua **dentro deste mesmo `Card`**, no fim,
  com o `borderTop` que já tem. Texto e estilo inalterados. O mockup os desenha sob um cabeçalho
  `SEMANA 4 · SCORECARD 71%`, mas `scorecard` vem de `getReviewWeekly()`, não de `getPontos()` — e
  esta tela não junta as duas fontes (ver seção 8, decisão nº 4).

### 2.3 O que sai

`conqHead`, `conqLabel`, `conqSaldo` (o rótulo "conquistas" e o saldo miúdo do canto — o herói os
substitui), `nivelRow` na forma antiga, `vitalicio`, `barTrack`, `barFill`, `semanaRow`,
`semanaLabel`, `ganho`, `desconto`, `proximo`. Estilo órfão é dívida: **apague de fato**, não deixe
comentado.

---

## 3. `app/src/screens/Revisao.tsx` — o título aparece duas vezes

`App.tsx` já desenha o cabeçalho das subtelas: `[‹ Voltar] [Revisão] [AETERNUM]`, com
`TITLES.revisao = "Revisão"` em `fonts.display` 20px. E `Revisao.tsx` desenha, logo abaixo, o
**seu próprio** `styles.head` com `<Text style={styles.title}>Revisão</Text>` e um badge. São dois
títulos empilhados dizendo a mesma palavra, um em Syne 20 e outro em Bricolage 21.

A Mesa não tem esse problema porque `isFull` esconde o cabeçalho do App nela. Aqui não dá para fazer
o mesmo: sem o cabeçalho do App não há chevron, e a subtela fica sem volta.

**Conserto:** apague o bloco `styles.head` inteiro de `Revisao.tsx` (a `View`, o `Text` do título e
o badge), mais os estilos `head`, `title`, `badge` e `badgeText`. O `<View style={{ flex: 1,
paddingTop: spacing.sm }}>` externo e o `ScrollView` ficam; tire o `marginTop: spacing.md` do
`ScrollView` se ele deixar um vão feio no topo — o herói já traz o próprio respiro.

**O número do badge não se perde.** Ele é `d?.count`, a contagem de cobranças. Ele vai para o rótulo
da seção que descreve exatamente isso, no padrão `.qgroup` do mockup (rótulo à esquerda, contagem à
direita, contagem em `faint`):

```tsx
<View style={styles.sectionHead}>
  <Text style={[styles.sectionLabel, { marginBottom: 0 }]}>cobranças de hoje</Text>
  <Text style={styles.sectionCount}>{d?.count ?? 0}</Text>
</View>
```

com `sectionHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between",
marginTop: spacing.lg, marginBottom: spacing.sm }` e `sectionCount: { fontFamily: fonts.mono,
fontSize: 9.5, color: colors.faint, letterSpacing: 1.4 }`.

Só essa seção. As outras (`objetivos acumulativos`, `cards Anki`, `ciclo de revisão`) ficam como
estão — duas delas já têm cabeçalho em linha com outros elementos, e mexer nelas não é desta onda.

---

## 4. Verificação (obrigatória antes de devolver o turno)

De dentro de `projects/escritorio/app`:

```
npm run typecheck
npm test
```

Os 85 testes de hoje continuam passando, mais os novos de `format.test.mjs`. Cole a **saída real**
dos dois.

---

## 5. Não regrida o que já está pago

- **Onda 1:** `SegmentBar`, `BigAction`, `RewardSheet`, `closingPoints.ts`. **Não abra.**
- **Onda 2:** `serif` não volta ao mapa `fonts`. `displayBold` (Syne 700) é só número-herói que
  chega pronto — este saldo é exatamente esse caso, e é o único `displayBold` desta tela.
- **Onda 3:** a Mesa, o `PendRow`, o `PointTag`, o `origem`/`BackHandler`. **Não toque em `App.tsx`,
  `Mesa.tsx`, `mesaView.ts`, `Tasks.tsx` nem `ui.tsx`.**
- O isolamento de estados de `Revisao.tsx` (`pontos` / `semanal` / `mensal` / `anki` /
  `readingPending` carregam e falham em separado) é blindagem de P0. **Não unifique nada.** Se um
  comentário explica um bug, mantenha o comentário.

---

## 6. Restrições

- Arquivos permitidos, e nada além: `app/src/format.ts` (novo), `app/tests/format.test.mjs` (novo),
  `app/src/screens/Revisao.tsx`, `app/src/screens/Home.tsx` (**uma linha só**, a do `milhar`).
- **Nada em `bff/`**, nada em `api.ts`, nada em `App.tsx`, nada em `ui.tsx`.
- **Nada de `git`**, nada de `npm install`.
- **Não delegue para subagentes**: no modo `-p` o processo morre quando você devolve o turno. Só
  devolva o turno depois de os arquivos estarem escritos.
- Não faça perguntas: decida pelo encargo e siga.

---

## 7. Na resposta final

Os arquivos tocados, qualquer divergência deste encargo com o motivo, e a saída real de
`npm run typecheck` e `npm test`.

---

## 8. Decisões já tomadas — não reabra

1. **Quatro diamantes, não seis.** O mockup desenha 6 (4 acesos). O tipo `Pontos` documenta
   `nivel: 0..4` e `proximo_nivel: null` significa "já está em N4". Seis diamantes prometeriam dois
   níveis que não existem. `NIVEIS = [1, 2, 3, 4]` **não muda**. Aqui o dado vence o frame.
2. **`SegmentBar` com os 10 segmentos padrão, não 12.** O mockup desenha 12 logo abaixo do rótulo
   `SEMANA 4/12` — mas a barra é alimentada por *pontos* (`ciclo.pontos / ciclo.meta`), não por
   semanas. Doze segmentos sob aquele rótulo seriam lidos como contador de semanas e mentiriam. E a
   Home, na onda 3a, já usa o padrão de 10 com o mesmo dado: divergir aqui criaria duas barras
   diferentes para a mesma grandeza.
3. **Saldo-herói em `colors.text`, não em bronze.** O mockup é explícito e a regra do sistema é um
   bronze cheio por tela — nesta tela ele fica nos diamantes e nos segmentos.
4. **O Placar não recebe `semanal`.** Os blocos `FECHAMENTOS / CAPTURAS / LEITURA` do frame vêm de
   `getReviewWeekly()`, e já existem logo abaixo, no cartão `Execução corrente`. O frame os mostra
   colados porque é uma tira de scroll só. Passar `semanal` para dentro do Placar acoplaria dois
   carregamentos que o arquivo separa de propósito.
5. **`Metrica` não é restilizada nesta onda.** O bloco `.stat` do mockup pede rótulo em caixa alta,
   mono 8.5, `letterSpacing: 1.4`. Medido: `FECHAMENTOS` assim ocupa ~71dp de texto; com o padding
   da caixa, ~87dp. São quatro caixas em `space-between` numa largura útil de ~296dp → ~68dp cada.
   Não cabe: o rótulo quebraria em duas linhas ou estouraria — o defeito nº 1 da onda 1 de novo.
   Fica registrado para uma decisão de design (cortar `staging`, encurtar os rótulos, ou três
   colunas), não para um chute.
6. **Sem `lineHeight` no herói.** Ver 2.1. Cortar glifo em Syne 54px é irreversível na tela.

---

## 9. O que sai da onda 4, e por quê

*(Registro para o Leo. Não é tarefa — não implemente nada desta seção.)*

### 9.1 O streak (`sequencia_atual` / `sequencia_recorde`) — adiado, não abandonado

O documento chama isto de "o único backend" e de "bônus declarado, nunca dependência". Confirmei que
o campo **não existe**: uma varredura em `bff/` por `sequencia|streak|recorde` não encontra nada
além de um `validar_sequencia` de chunks de upload e de um teste que proíbe a *palavra* "streak" nos
textos de cobrança. Escrever a peça é escrever o cálculo do zero em `pontos.py`.

Três motivos para não fazer agora, em ordem de peso:

1. **A economia de pontos está em contradição aberta — e a distância é maior do que eu vinha
   dizendo.** Fui conferir a fonte antes de escrever isto. O BFF tem **uma única forma de ganhar
   ponto**: `ganho = feitos * pontos_por_rotina` (`bff/app/pontos.py:195`), com
   `pontos_por_rotina = 1` (`bff/app/config.py:73`) — ou seja, **1 ponto por rotina marcada como
   feita no fechamento, e nada mais**. Tarefa concluída não paga. Captura não paga. Fechar o dia
   não paga. Shutdown não paga. Despejo não paga.

   A tabela `POINTS` do app (tarefa 10, rotina 20, captura 5, fechamento 80, shutdown 30,
   despejo +40) não é uma moeda com um valor errado: ela **não existe do outro lado**. O saldo que
   esta onda promove a herói de 54px é, literalmente, *quantas rotinas você já marcou como feitas,
   menos os descontos de padrão*. É um número verdadeiro — só não é o número que os rótulos "vale
   +80" prometem.

   Somar um streak em cima disso é construir o segundo andar antes do primeiro. Streak e
   reconciliação da economia tocam o **mesmo módulo** e devem ser uma mudança pensada, não duas.
2. **É o BFF de produção do Leo, e ele grava no vault dele.** Mexer ali pede uma sessão com teste
   de verdade, não um encargo de restyling.
3. Fora do escopo do kimi por regra permanente desta série de ondas: outra sessão trabalha no mesmo
   repositório e `bff/` é dela.

O compromisso do documento continua honrado do jeito certo: **nenhum número inventado.** A
RewardSheet e o Placar simplesmente não mostram a linha enquanto o campo não existir — que é
exatamente o estado de hoje.

### 9.2 O polimento de `Abertura.tsx` / `Capture.tsx` — cortado, precisa de desenho antes

A onda pede *"TemplateCards e toasts quietos ('capturado · +5 · saldo') no mesmo padrão da
RewardSheet"*. Três achados contra:

1. **Nenhuma das duas telas tem frame desenhado na proposta.** A regra que vem valendo desde a onda
   2 é "o frame desenhado vence a prosa"; aqui não há frame nenhum, só uma linha de prosa numa
   tabela de plano. Não é design, é intenção.
2. **O toast, como especificado, precisa do saldo — e `Capture.tsx` não o tem.** Mostrar
   "capturado · +5 · saldo" exigiria um `getPontos()` novo no caminho mais quente do app (capturar
   tem que ser instantâneo), e o "+5" viria da tabela `POINTS`, que é display-only e que o BFF não
   honra. Seria inventar número no exato lugar onde a proposta promete não inventar.
3. **`Capture.tsx` é o arquivo mais perigoso do app**: fila offline com `client_key` idempotente,
   máquina de estados de rascunho de leitura, verificação por hash, escrita no vault. Ele já tem
   confirmação de sucesso (`setReply`). Restyling sem desenho e sem teste, ali, é como se quebra a
   coisa que guarda as notas do Leo.

Se o Leo quiser o polimento, o caminho é um frame desenhado para as duas telas primeiro — e aí é
uma onda 5 pequena, não um apêndice desta.
