# Encargo — Onda 3b: pontos discretos em Tarefas (e três consertos da 3a)

A onda 3a (A Mesa) está entregue e revisada. Esta é a segunda metade da onda 3 da
`proposta-c2-sobria.html`: **os pontos na lista de Tarefas**, mais três consertos que a revisão da
3a levantou.

O critério de aceite desta onda está escrito no próprio mockup, e é visual:

> **Na lista cheia, a coluna de pontos não pode criar textura.** Se algum "+10" chamar atenção
> antes do nome da tarefa, a tela está errada — e é por isso que o mockup a desenha com 12 itens,
> não com 3.

Isso quer dizer: **sem pill, sem fundo, sem accent enquanto a linha está aberta.** O `+10` em
repouso tem exatamente a mesma cor e peso do metadado de prazo ao lado. Ele é datilografia, não
decoração. Foi badge colorido que afundou a rodada D.

**Não delibere: as decisões estão todas aqui.** Comece pelo item 1 e siga a ordem.

---

## 1. `app/src/theme.ts` — o Shutdown ganha preço

`POINTS` ganha uma chave: `shutdown: 30`.

Motivo: o hero da Home mostra "vale +80" no Fechar e "+20" na Abertura, e não mostrava nada no
Shutdown — que é o rito das 19h. O 30 é o número do próprio mockup aprovado. A tabela inteira já é
**provisória e display-only**, declarada assim em comentário; isto é rótulo novo, não moeda nova.
Não mexa em nenhum outro valor, e não toque em `bff/`.

---

## 2. `app/src/mesaView.ts` — a garantia anti-órfão passa a ser estrutural

Hoje o módulo decide o grupo de `triagem` e `revisao` com **duas condições escritas em separado**
que por acaso se completam (`n > 0` para "precisa", `n === 0` para o arquivo). Se o BFF mandasse
`n` negativo, as duas seriam falsas, a Triagem sumiria da Mesa — e como a grade "Ferramentas" foi
apagada na 3a, a tela ficaria **inalcançável**. É exatamente o desastre que esta onda existe para
impedir, e a varredura de 1.296 combinações não testa negativo.

**Conserto:** uma constante booleana por item, usada nos dois lados. `if (x) precisa` … `if (!x)
arquivo`, com o **mesmo `x`** — nunca duas expressões independentes. A ordem dos grupos e do arquivo
não muda; só a forma da decisão.

```ts
const triagemNaFila = !!sinais.triagem && sinais.triagem.n > 0;
const ankiNaFila = sinais.anki !== null && sinais.anki > 0;
const leiturasNaFila = sinais.leituras !== null && sinais.leituras > 0;
```

E `valorDaAcao` ganha o caso novo: `case "shutdown": return points.shutdown;`. O tipo
`PointsTable` do módulo ganha `shutdown: number` junto.

### O teste, primeiro

Em `app/tests/mesaView.test.mjs`, **antes** de mexer no módulo:

1. Acrescente à varredura anti-órfão as variantes negativas — `triagem: { n: -1, maisVelhoD: null }`
   e `anki: -1` — e ajuste a contagem de combinações no final do teste.
2. Rode e **veja falhar** (hoje a Triagem some com `n: -1`). Só então aplique o conserto do módulo.
3. Acrescente `assert.equal(valorDaAcao("shutdown", POINTS), POINTS.shutdown)` e **tire** `"shutdown"`
   da lista do teste que espera `null`.

---

## 3. `app/src/screens/Home.tsx` — o ciclo aparecia duas vezes

A 3a subiu o ciclo para o cartão de saldo ("CICLO 3 · S4/12"), mas a fita de stats logo abaixo
continuou com a coluna "CICLO". No mockup aprovado a fita é **RITMOS · COBRANÇAS · FOCO** — o ciclo
saiu de lá justamente porque subiu.

**Troque a coluna do meio (CICLO) por FOCO:**

- rótulo `FOCO` no mesmo `metricLabel` das outras;
- corpo: o nome da primeira tarefa (`focus[0].name`) em `fonts.uiSemi` ~13px, `numberOfLines={2}`.
  **Não use `metricValue`** — ele é `fonts.display` 21px, tamanho de número-herói; nome de tarefa em
  Syne 21px é exatamente o erro que a onda 2 evitou. Crie um estilo próprio (`metricFocus`).
- rodapé: `AREA · PRAZO` em `fonts.mono` ~8.5px na cor da área (`areaColor(task.area)`), caixa alta.
- toque: `onOpenTab?.(\`tarefa:${focus[0].id}\`)`, como as linhas da seção "Foco de hoje" já fazem.
- **sem tarefa** (ou `digest` não carregado): rótulo `FOCO`, corpo `—` em `metricValue`, rodapé
  `nada no radar` em `metricHint`. Não invente tarefa nem esconda a coluna.

Nada mais muda na Home.

---

## 4. `app/src/ui.tsx` — `PointTag` e um `meta` no `SectionHeader`

### `PointTag`

```tsx
export function PointTag({ pontos, aceso = false }: { pontos: number; aceso?: boolean })
```

- **Repouso:** `fonts.mono`, fontSize **10.5**, cor **`colors.faint`**, `width: 34`,
  `textAlign: "right"`. A largura fixa é o que faz doze linhas virarem uma régua quieta em vez de
  uma serrilha. Texto: `+${pontos}`.
- **Aceso** (`aceso` vira `true`): cor `colors.success`, sobe **12px** esmaecendo até 0, com
  `Animated.timing` de **350ms**, `useNativeDriver: true`. Menos de 400ms, como toda animação deste
  sistema. Use `useRef(new Animated.Value(0))` + `useEffect` no padrão do `QuestRow` da onda 1.
- **Nunca** pill, fundo, borda ou bronze. Em repouso ele tem que ficar visualmente idêntico ao
  metadado de prazo ao lado.

### `SectionHeader` ganha `meta`

Prop opcional `meta?: string`, renderizada à direita em `fonts.mono` ~9.5px `colors.faint` —
**apenas quando não houver `action`/`onAction`** (o slot da direita é um só; `action` continua
vencendo). Não é pressionável: é fato, não botão.

---

## 5. `app/src/screens/Tasks.tsx` — a coluna, o flash e a confirmação

### 5.1 A coluna de pontos

No `TaskRow` aberto (o `return` de baixo, não o de confirmação), insira o `PointTag` **entre o
`taskBody` e a seta** `arrow-up-right`: `[check] [corpo] [+10] [↗]`. Valor: `POINTS.tarefa`.

Não mexa em mais nada da linha. Em particular, `severityColor()` continua mandando na cor do
checkbox (atrasada em `danger`, o resto na cor da área) — **essa é a única cor que sobra na lista**.

### 5.2 O flash

Ao **confirmar** a conclusão (o segundo toque, o que chama `completeById`), a linha acende: check
enche de sálvia e o `+10` faz o movimento do `PointTag` aceso.

**O flash dispara no toque, imediatamente — não ao voltar do servidor.** Este arquivo já carrega a
lição em comentário (`Tasks.tsx:44-46`): a confirmação nasceu dentro da linha porque tocar num item
sem feedback fazia parecer que o app ignorou o toque. Esperar a rede reintroduz esse silêncio.
A linha sai da lista quando o `load(true)` volta; se a conclusão falhar de verdade, o `Alert` que já
existe corrige — e no caso offline a conclusão foi enfileirada, então o flash disse a verdade.

Estado novo: um `flashId: string | null` (ou reuse `completingId`, se bastar) para saber qual linha
acende. Limpe-o depois da animação.

### 5.3 A confirmação mostra o valor

O ramo `confirmando` do `TaskRow` (`CONCLUIR? / cancelar / ✓`) ganha o valor visível: o `+10` em
`PointTag` ao lado do "CONCLUIR?", para o toque decisivo dizer o que ele paga. Mantenha o alvo do
`confirmOk` e o `ActivityIndicator` do estado `concluindo` **exatamente como estão** — eles são
mecânica de toque já testada no uso.

### 5.4 O agregado do grupo

`SectionHeader` da seção **"Agora"** ganha `meta={\`+${grouped.agora.length * POINTS.tarefa} na mesa\`}`.
Só nessa seção — é o único agregado da tela, como no mockup. Quando o grupo estiver vazio a seção
já não renderiza, então não há caso de `+0`.

---

## 6. Não regrida o que já está pago

- **Onda 1:** o `flexShrink: 1` + `numberOfLines={1}` do `BigAction`; a constante única `temTexto`
  do `Fechar.tsx`; `closingPoints.ts` e seu teste — **não abra**.
- **Onda 2:** `serif` não volta ao mapa `fonts`. Nome de tarefa é `uiSemi`, contador é `mono`,
  título de tela é `display`.
- **Onda 3a:** a Mesa, o `PendRow`, o `origem`/`BackHandler` do `App.tsx`. **Não toque em
  `App.tsx` nem em `Mesa.tsx` nesta onda.**
- `completeById` guarda um tratamento de rede real (fila offline, alerta só para erro de servidor).
  **Não reescreva essa função** além do que o flash exigir. Se um comentário explica um bug,
  mantenha o comentário.

---

## 7. Verificação (obrigatória antes de devolver o turno)

De dentro de `projects/escritorio/app`:

```
npm run typecheck
npm test
```

Os 85 testes atuais têm que continuar passando, incluindo a varredura anti-órfão com as variantes
negativas novas. Cole a **saída real** dos dois.

---

## 8. Restrições

- Arquivos permitidos, e nada além: `app/src/theme.ts`, `app/src/mesaView.ts`,
  `app/tests/mesaView.test.mjs`, `app/src/ui.tsx`, `app/src/screens/Tasks.tsx`,
  `app/src/screens/Home.tsx`.
- **Nada em `bff/`**, nada em `api.ts`, nada em `App.tsx`, nada em `Mesa.tsx`.
- **Nada de `git`**, nada de `npm install`.
- **Não delegue para subagentes**: no modo `-p` o processo morre quando você devolve o turno. Só
  devolva o turno depois de os arquivos estarem escritos.
- Não faça perguntas: decida pelo encargo e siga.

Na resposta final: os arquivos tocados, como fez o flash disparar (e onde limpou o estado),
qualquer divergência deste encargo com o motivo, e a saída real de `npm run typecheck` e `npm test`.
