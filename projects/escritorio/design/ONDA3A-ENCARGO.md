# Encargo — Onda 3a: A Mesa (e a Home que perde a gaveta)

Ondas 1 e 2 estão entregues e verificadas. A proposta aprovada junta numa "onda 3" duas coisas
independentes: **a Mesa** (tela nova + 5ª aba + cirurgia na Home) e **os pontos em Tarefas**. Aqui
vai só a primeira. Motivo: a Mesa tem um risco que os pontos não têm — se ela não cobrir tudo que a
grade "Ferramentas" cobria, telas inteiras do app ficam **inalcançáveis**. Isso merece revisão
própria. Os pontos em Tarefas vêm na 3b.

---

## 1. O coração: uma regra pura, testada — não uma tela esperta

A Mesa é **ordenação e agrupamento**. Isso é lógica, e neste repositório lógica mora em `src/*.ts`
puro com teste em `tests/*.test.mjs`. A tela só desenha o que o módulo devolve.

Crie **`app/src/mesaView.ts`**, módulo puro. Regra do repositório, que já mordeu na onda 1: o Node
tira os tipos sozinho, mas **não resolve import relativo em runtime** — então o módulo não pode ter
nenhum `import` de valor. `import type` é permitido (é apagado). Se precisar da tabela `POINTS`, ela
entra **por parâmetro**, e o teste é quem importa `../src/theme.ts` — assim os valores de produção
ficam presos ao teste.

### Os tipos

```ts
// O que a tela conseguiu carregar. null = NÃO CARREGOU, e null nunca vira estado.
export type MesaSinais = {
  triagem: { n: number; maisVelhoD: number | null } | null;
  anki: number | null;
  leituras: number | null;
  aberturaFeita: boolean | null;
  shutdownFeito: boolean | null;
  ritmos: { feitos: number; total: number } | null;
};

export type MesaItem = {
  destino: string;      // o que vai para openDestination()
  nome: string;
  sub: string;
  contador: string | null;  // texto curto à direita ("3", "5/8", "21h") ou null
  feito: boolean;           // true → a tela desenha "FEITO ✓" em sálvia no lugar do contador
};

export type MesaGrupo = { titulo: string; itens: MesaItem[] };

export function montarMesa(sinais: MesaSinais, points: PointsTable): MesaGrupo[];
```

### A regra de ordenação — explícita e estável

Três grupos, sempre nesta ordem: **`PRECISA DE VOCÊ` → `ROTINA DO DIA` → `ARQUIVO`**.

**`PRECISA DE VOCÊ`** — só entra quem tem trabalho parado agora:

| item | entra quando | sub | contador |
|---|---|---|---|
| Triagem (`triagem`) | `triagem.n > 0` | `mais velho há Nd` — e se `maisVelhoD` for null, `N itens parados` | `n` |
| Revisão (`revisao`) | `anki > 0` | `N cartões anki sugeridos` | `anki` |
| Leituras (`leitura`) | `leituras > 0` | `N sessão(ões) por fechar` | `leituras` |
| Shutdown (`shutdown`) | `shutdownFeito === false` | `rito das 19h · fecha o trabalho` | `19h` |
| Fechar o dia (`fechar`) | **sempre** | `rito das 21h · vale +N` (`points.fechamento`) | `21h` |

**`ROTINA DO DIA`** — o que tem estado conhecido:

| item | entra quando | sub | contador / feito |
|---|---|---|---|
| Abertura (`abertura`) | `aberturaFeita !== null` | feita: `check-in do dia feito` · não: `o dia ainda não foi aberto` | `feito: aberturaFeita` |
| Shutdown (`shutdown`) | `shutdownFeito === true` | `trabalho fechado` | `feito: true` |
| Ritmos (`rotinas`) | `ritmos !== null` | `N de M hoje` | `N/M`, `feito` quando `N === M && M > 0` |

**`ARQUIVO`** — o resto, sempre presente, sempre nesta ordem:
`agenda` (Agenda) · `triagem` **se `n === 0` ou null** · `revisao` **se `anki === 0` ou null** ·
`habitos` (Reduzir) · `edificacao` (Edificação) · `melhorias` (Melhorias) · `rotinas` **se
`ritmos === null`** · `abertura` **se `aberturaFeita === null`** · `shutdown` **se
`shutdownFeito === null`** · `settings` (Ajustes).

Subs do arquivo: texto fixo e curto, sem número (`semana e horários`, `hábitos a reduzir`,
`projetos de longo prazo`, `a fila de melhorias`, `ajustes do app`). Contador `null`.

Grupo vazio **não aparece** — `montarMesa` não devolve grupo com `itens: []`.

### O teste — e o caso que importa mais que todos

`app/tests/mesaView.test.mjs`, **TDD: escreva, rode, veja falhar, depois implemente.**

Cubra os casos normais (cada item indo para o grupo certo em cada estado). E cubra este, que é o
critério de aceite duro da onda:

> **Nenhum destino órfão.** Para *qualquer* combinação de sinais — tudo carregado, nada carregado,
> tudo zerado, tudo cheio —, a união dos três grupos contém **os onze destinos** que a grade
> "Ferramentas" cobria hoje: `agenda`, `abertura`, `triagem`, `rotinas`, `habitos`, `revisao`,
> `edificacao`, `melhorias`, `shutdown`, `fechar`, `settings`.

Escreva esse teste varrendo combinações de verdade (inclusive `sinais` com todos os campos `null`),
não um caso só. Se um destino sumir em alguma combinação, a tela dele fica **inalcançável no app** —
é o único jeito desta onda causar dano real.

Cubra também: **nenhum destino duplicado** entre grupos (Triagem não pode estar em "precisa de
você" e no arquivo ao mesmo tempo).

---

## 2. `app/src/ui.tsx` — o `PendRow`

Um componente, no padrão do `QuestRow` da onda 1:

- Linha `Pressable` de **altura mínima 56px**, `accessibilityRole="button"`.
- **Ícone à esquerda** em quadrado ~32px, `borderRadius` ~10, fundo `${cor}19` — a cor semântica
  vem por prop (é o único lugar com cor nesta tela).
- Nome em `fonts.uiSemi` ~13.5px; sub em `fonts.ui` ~11.5px `colors.textMuted`.
- **Contador à direita em `fonts.mono` ~11px na cor do texto. Sem pill, sem fundo, sem accent** —
  foi exatamente a pill colorida que o Leo rejeitou na variação C. Se o contador for número puro,
  ele é datilografia.
- Estado feito: no lugar do contador, `FEITO ✓` em `fonts.mono` ~9px, `colors.success`, caixa alta.
- Variante `idle` (arquivo): a linha inteira a ~50% de opacidade, ícone em `colors.textMuted`.

Nome e sub precisam de `numberOfLines={1}` e `flexShrink: 1` — o defeito nº 1 da onda 1 foi
exatamente isto, e aqui há contador disputando a mesma linha.

**Enquanto estiver em `ui.tsx`, conserte um comentário que a onda 2 deixou mentindo:** o bloco acima
de `RewardSheet` (~linha 346) ainda diz *"Tipografia atual de propósito — display/Syne é onda 2"*.
A onda 2 aconteceu; o herói já é `fonts.displayBold`. Reescreva a frase para o que é verdade agora.

---

## 3. `app/src/screens/Mesa.tsx` (novo)

Tela burra: carrega, monta os sinais, chama `montarMesa`, desenha grupos de `PendRow`.

**Carregamento** — siga o padrão que a `Home.tsx` já usa (`run()` com `Promise.race` de timeout de
6s por chamada, `loaded`/`failures` em `Set`, `RefreshControl`, recarga no `AppState "active"`).
Leia a Home antes de escrever: o padrão está pronto e testado no uso, não invente outro.

Chamadas: `getTriagem()`, `listAnkiCards("sugerido")`, `listPendingReadingSessions()`,
`getAbertura()`, `getShutdown()`. Cada uma que falhar vira `null` no `MesaSinais` — **falha parcial
não derruba a tela**, e o item cai no arquivo em vez de mentir um estado.

Cabeçalho: eyebrow `sistema` em mono + título `A Mesa` em `fonts.display` (o `.scr-title` do
mockup). Cabeçalho de grupo: mono caixa alta em `colors.textMuted`, com o total à direita quando
houver (`3`).

`onOpenTab` entra por prop, igual à Home, e o destino vai direto para `openDestination`.

---

## 4. `app/App.tsx` — a 5ª aba, e a volta que não mente

1. `Tab` ganha `"mesa"`. `TABS` ganha o 5º item: `{ key: "mesa", label: "Mesa", icon: "grid" }`.
   `mesa` **não** entra em `SUBSCREENS` (é aba, não subtela) e não precisa de entrada em `TITLES`.
2. Renderize `<Mesa onOpenTab={openDestination} />` no mesmo `switch` da Home.
3. **A volta das subtelas.** A proposta manda o chevron voltar para a Mesa. Faça melhor e mais
   barato: guarde de onde veio. Um `useState<Tab>("home")` (`origem`), gravado dentro de
   `openDestination` **antes** de trocar de aba quando o destino for subtela; o chevron e o
   `BackHandler` passam a usar `origem` em vez do literal `"home"`.
   Assim: entrou pela Mesa, volta para a Mesa; entrou por uma notificação das 21h, volta para Hoje.
   Voltar sempre para a Mesa deixaria a notificação desembocando numa tela que o Leo não pediu.
   O `BackHandler` continua devolvendo `false` (deixa o Android sair) só quando já está em `home`.

**Risco a conferir, não a supor:** a tabbar passa de 4 para 5 itens. Cada `tabItem` é `flex: 1` com
`gap: 4` e `paddingHorizontal: spacing.sm`. Num aparelho de 360dp isso dá ~65dp por aba, e o rótulo
mais longo é "Capturar" em `fonts.ui` 10px. **Meça antes de aceitar** (ou reduza o rótulo, nunca o
alvo de toque — `minHeight: 52` fica). Diga na resposta o que mediu.

---

## 5. `app/src/screens/Home.tsx` — sai a gaveta, entra o saldo

1. **Apague a seção "Ferramentas"** inteira (o `SectionHeader` + a grade de 11 botões, hoje
   ~linhas 260–288, mais os estilos `tools`/`tool`/`toolIcon`/`toolLabel` que ficam órfãos).
   A Home termina na agenda curta. **Só apague depois que a Mesa existir e o teste anti-órfão
   passar** — é a única ordem segura.
2. **Entra, logo abaixo da saudação, o cartão de saldo:** saldo em `fonts.mono` (~15px) com `PTS` em
   `faint` ao lado, `CICLO N · SM/12` em mono `faint` à direita, e a `SegmentBar` (bronze) do ciclo
   embaixo. Dados: `points.saldo_total` e `points.ciclo`, que a tela **já carrega**. O saldo é mono
   de propósito: ele re-soma quando a Home recarrega no `AppState "active"`, e número que se move à
   vista fica tabular.
3. **O hero ganha o preço:** ao lado do "abrir agora", `vale +N` em `fonts.mono` ~10px `faint`.
   O N sai de uma função pura nova em `mesaView.ts` — `valorDaAcao(target, points)` — que mapeia o
   `action.target` do `actionForAt()` para a tabela `POINTS` (`fechar` → `fechamento`, `rotinas`/
   `abertura` → `rotina`, `capturar`/`leitura` → `captura`, `tarefas` → `tarefa`, resto → `null`).
   **Quando devolver `null`, a tela não desenha nada** — não escreva "vale +0".
   Teste essa função junto com o resto.

Não mexa em mais nada da Home. Em particular: `actionForAt`, o dock de captura e a lógica de
`loaded`/`failures` ficam como estão.

---

## 6. Honestidade de dados — o que NÃO inventar

- **Não existe flag de "fechamento feito".** O BFF não expõe. Por isso "Fechar o dia" fica sempre em
  "precisa de você", com a hora e o valor, e **nunca** com "FEITO ✓". É a mesma lei do streak da
  onda 1: nenhum número, nenhum estado inventado.
- **`null` é desconhecido, não é zero.** Sinal que não carregou manda o item para o arquivo, sem sub
  numérico. Nunca escreva "0 itens" a partir de uma falha de rede.
- **`POINTS` continua provisória e display-only.** O app anuncia +80 pelo fechamento e o BFF real
  paga 0 — isso é onda própria, decidida pelo Leo. Não toque em `bff/`, não mude os valores.

---

## 7. Não regrida ondas 1 e 2

- `Fechar.tsx`: a constante única `temTexto` e os comentários que explicam bugs antigos.
- `ui.tsx`: o `flexShrink: 1` + `numberOfLines={1}` do `BigAction`.
- `theme.ts`: o mapa `fonts` da onda 2 — **não adicione `serif` de volta**, e use `fonts.display`
  para título de tela, `uiSemi` para nome de linha, `ui` para sub, `mono` para contador.
- `closingPoints.ts` e seu teste: **não abra**.

---

## 8. Verificação (obrigatória antes de devolver o turno)

De dentro de `projects/escritorio/app`:

```
npm run typecheck
npm test
```

Os 71 testes atuais têm que continuar passando, mais os seus novos. Cole a **saída real** dos dois.

---

## 9. Restrições

- Arquivos permitidos: `app/src/mesaView.ts` (novo), `app/tests/mesaView.test.mjs` (novo),
  `app/src/screens/Mesa.tsx` (novo), `app/src/ui.tsx`, `app/App.tsx`, `app/src/screens/Home.tsx`.
  **Nada além disso.**
- **Nada em `bff/`.** Nada em `Tasks.tsx` (é a onda 3b). Nada em `api.ts` — tudo que a Mesa precisa
  já existe; se você achar que falta uma chamada, **diga na resposta em vez de criar**.
- **Nada de `git`**, nada de `npm install`.
- **Não delegue para subagentes**: no modo `-p` o processo morre quando você devolve o turno. Só
  devolva o turno depois de os arquivos estarem escritos.
- Não faça perguntas: decida e siga, e explique as decisões na resposta final.

Na resposta final: os arquivos tocados, o teste anti-órfão que escreveu (cole-o), a medição da
tabbar de 5 abas, qualquer ponto onde divergiu deste encargo e por quê, e a saída real de
`npm run typecheck` e `npm test`.

---

## 10. Decisões já tomadas — não delibere, execute

Toda escolha de projeto desta onda já está feita abaixo. **Não gaste turno planejando: comece
escrevendo `tests/mesaView.test.mjs`.**

**Ordem de execução, nesta sequência:** (1) o teste; (2) rodar e ver falhar; (3) `mesaView.ts`;
(4) rodar e passar; (5) `PendRow` + o comentário velho no `ui.tsx`; (6) `Mesa.tsx`; (7) `App.tsx`;
(8) `Home.tsx`; (9) typecheck e testes.

**`PointsTable`** — declare no próprio `mesaView.ts`, estrutural, sem `despejoBonus` (o `POINTS`
real é atribuível a ela):
```ts
export type PointsTable = { tarefa: number; rotina: number; captura: number; fechamento: number };
```

**Plural:** singular quando for 1. `1 item parado` / `3 itens parados`; `1 cartão anki sugerido` /
`4 cartões anki sugeridos`; `1 sessão por fechar` / `2 sessões por fechar`.

**Subs fixos do arquivo** (sem número, exatamente estes):
`agenda` → `semana e horários` · `triagem` → `a fila de entrada` · `revisao` → `cartões e revisão` ·
`habitos` → `hábitos a reduzir` · `edificacao` → `projetos de longo prazo` · `melhorias` →
`a fila de melhorias` · `rotinas` → `os ritmos do dia` · `abertura` → `abrir o dia` · `shutdown` →
`fechar o trabalho` · `settings` → `ajustes do app`.

**Nomes:** Triagem · Revisão · Leituras · Shutdown · Fechar o dia · Abertura · Ritmos · Agenda ·
Reduzir · Edificação · Melhorias · Ajustes.

**Cabeçalho de grupo:** título à esquerda, `itens.length` à direita, os dois em mono.

**De onde vem cada sinal** (`Mesa.tsx`):
- `triagem.n` ← `getTriagem().n`
- `triagem.maisVelhoD` ← `getShutdown().staging.mais_velho_d`. Se o shutdown falhar e a triagem
  não, o sinal fica `{ n, maisVelhoD: null }` e o sub cai para `N itens parados`. **Não invente.**
- `anki` ← `listAnkiCards("sugerido").length` · `leituras` ← `listPendingReadingSessions().sessions.length`
- `aberturaFeita` ← `getAbertura().checkin.feito` · `ritmos` ← `getAbertura().rotinas_manha`
- `shutdownFeito` ← `getShutdown().feito`

**Ícone e cor por destino** (são os mesmos da grade antiga da Home — a Mesa herda, não reinventa):
`agenda` calendar/info · `abertura` sunrise/lilac · `triagem` inbox/amber · `rotinas` repeat/success ·
`habitos` trending-down/info · `revisao` compass/primary · `edificacao` layers/lilac ·
`melhorias` zap/amber · `shutdown` sunset/primary · `fechar` moon/info · `settings` settings/textMuted ·
`leitura` book-open/primary. Esse mapa mora em `Mesa.tsx`, não no módulo puro.

**A Mesa não usa o header do App.** Ela tem cabeçalho próprio (eyebrow `sistema` + `A Mesa` em
`fonts.display`), então dois títulos empilhados seria erro. No `App.tsx`: o header passa a esconder
com `tab !== "home" && tab !== "mesa"`, e `isFull` passa a incluir `mesa` — a Mesa põe o próprio
`paddingHorizontal: spacing.lg`, como a Home faz.

**Ordem da tabbar:** `Hoje · Mesa · Capturar · Tarefas · Mentor`. A Mesa em segundo porque é ela que
substitui a gaveta que sai da Home.

**`BackHandler`**, exatamente assim — `origem` sozinha criaria armadilha (voltar da Mesa para a Mesa
e o Android nunca sair do app):
```ts
if (tab === "home") return false;
setTab(SUBSCREENS.includes(tab) ? origem : "home");
return true;
```
E `origem` entra nas dependências desse `useEffect`. O chevron (que só existe em subtela) usa
`origem` direto, e o `accessibilityLabel` dele deixa de dizer "Voltar para Hoje" — passa a ser só
`Voltar`, porque agora o destino varia.

**O cartão de saldo da Home** só renderiza quando `loaded.has("points")` e `points` existe. Falha de
rede não vira saldo zero.
