# Pré-voo no aparelho — as quatro ondas, uma passada só

As ondas 1–4 da `proposta-c2-sobria.html` estão escritas e **nunca foram executadas**. `tsc` e
`node --test` não pegam layout quebrado, fonte que não carrega, nem tela que estoura ao montar.

O que **já foi liquidado por script**, e portanto você não precisa procurar:

| checagem | resultado |
|---|---|
| `npm run typecheck` | limpo |
| `npm test` | 88/88 |
| os 7 nomes de `fonts` no `theme.ts` × os 7 do `useFonts` | batem exatamente, sem sobra nem falta |
| os 12 nomes de ícone Feather do mapa `VISUAL` da Mesa (o `as keyof` desliga o typecheck neles) | todos existem no glyphmap |
| estilos órfãos nos 7 arquivos tocados | só 2, e já estavam no `HEAD` — código morto anterior |
| `a?.b.c` com o opcional parando cedo demais | os 3 novos são seguros: `ciclo`, `staging` e `checkin` são obrigatórios no tipo |
| bundle do Metro (`expo export --platform android`) | **886 módulos, 2.94 MB de bytecode Hermes, exit 0** — compila no Hermes, não só no `tsc` |

```
npx expo start --android
```

---

## A ordem de olhar, do mais arriscado para o menos

### 1. Mesa — a aba nova, que nunca foi renderizada em lugar nenhum

O maior risco do pacote inteiro: tela nova, aba nova, e o único caminho para 11 destinos depois que
a grade "Ferramentas" saiu da Home.

- **Os três grupos aparecem?** `PRECISA DE VOCÊ` → `ROTINA DO DIA` → `ARQUIVO`. Grupo vazio não
  deve renderizar.
- **Conte os destinos.** Têm que ser 11, sem repetir: agenda, abertura, triagem, rotinas, habitos,
  revisao, edificacao, melhorias, shutdown, fechar, settings — mais leitura quando houver sessão.
  O teste varre 2160 combinações de sinais garantindo isso, mas ele testa o módulo puro, não a tela.
- **A tabbar com 5 abas num aparelho estreito.** `Hoje · Mesa · Capturar · Tarefas · Mentor`. O
  rótulo mais longo é "Capturar". Cálculo diz ~65dp por aba em 360dp; se truncar, é aqui.
- **O botão físico de voltar.** Da Mesa tem que **sair do app** (não voltar para a Mesa). De uma
  subtela aberta pela Mesa, tem que voltar para a Mesa. De uma subtela aberta pela Home, para a Home.
- **Com o BFF fora do ar:** a faixa "alguns dados não responderam · atualizar" aparece, e os itens
  caem no ARQUIVO em vez de inventar número. Nenhum sinal desconhecido pode virar "0".

### 2. Tarefas com 12+ itens — o critério de aceite da onda 3b, escrito no mockup

> *Na lista cheia, a coluna de pontos não pode criar textura.*

Se algum `+10` chamar atenção **antes** do nome da tarefa, a tela está errada. Em repouso o `+10`
tem que ser indistinguível do prazo ao lado: mesma cor (`faint`), mesmo peso, alinhado em coluna de
34px. A única cor que sobra na lista é o fio do checkbox.

Toque para concluir: o check enche de sálvia e o `+10` sobe esmaecendo, **no toque**, não quando o
servidor responde.

### 3. Revisão → o Placar

- **O saldo de 54px em Syne 700 corta glifo?** Foi o motivo de eu proibir `lineHeight` ali. Se
  cortar mesmo assim, o conserto é `lineHeight: 66` no `heroSaldo`.
- **Um título só.** Antes desta onda a palavra "Revisão" aparecia duas vezes, empilhada — uma no
  cabeçalho do App em Syne 20 e outra dentro da tela em Bricolage 21.
- **Quatro diamantes, não seis** (o mockup desenhou 6; o tipo diz `nivel: 0..4`).
- O respiro dentro do cartão do ciclo soma o `gap` do `Card` às margens internas: as folgas reais
  são 18 e 20dp, não 10 e 12. Deixei assim de propósito — é preferência, e só aqui dá pra decidir.

### 4. Hoje — o que a onda 3a mexeu

Cartão de saldo no topo, `vale +N` no hero, e a coluna do meio da fita virou **FOCO** (era CICLO,
que subiu para o cartão). Sem tarefa, ela lê `—` / `nada no radar` — não pode sumir nem inventar.

### 5. Fechar — a onda 1, a de maior frequência

Um primário de 60px sempre habilitado com a recompensa escrita no botão; rotinas como QuestRows; a
RewardSheet no fim. **Sem linha de streak** — o BFF não expõe sequência, e nenhum número se inventa.

---

## As quatro perguntas que só a tela responde — e a saída de cada uma

Todas as saídas são de uma linha no `theme.ts`.

| pergunta | se der errado |
|---|---|
| A Bricolage 400 sustenta o corpo, ou ficou leve demais? | `ui: "BricolageGrotesque_500Medium"` — o `uiMedium` já está carregado |
| A Syne briga com a Bricolage? | `display: "Fraunces_600SemiBold"` — a Fraunces continua instalada de propósito |
| O `+10` cria textura na lista cheia? | baixar `pointTag.fontSize` ou aproximar mais a cor do `faint` |
| O herói de 54px corta glifo? | `lineHeight: 66` no `heroSaldo` do `Revisao.tsx` |

Só depois de a tipografia estar decidida é que a Fraunces e a Space Grotesk saem do
`package.json` — elas estão ali como escotilha barata, não por esquecimento.

---

## O que ficou de fora das ondas, de propósito

- **Streak** (`sequencia_atual` / `sequencia_recorde`): não existe no BFF. Motivo do adiamento na
  seção 9.1 do `ONDA4-ENCARGO.md` — resumo: a economia de pontos precisa ser reconciliada primeiro,
  e as duas coisas mexem no mesmo módulo.
- **Polimento de Capturar/Abertura**: nenhuma das duas tem frame desenhado na proposta, e o toast
  especificado precisaria de um `getPontos()` no caminho mais quente do app. Seção 9.2.
- **`Metrica` no visual de stat block**: não cabe em 4 colunas num aparelho de 360dp. Medição na
  decisão nº 5 do `ONDA4-ENCARGO.md`.

---

## Achado do bundle: 2,3 MB de fonte morta (para a sessão de limpeza, não para agora)

A lista de assets do `expo export` mostra **26 arquivos `.ttf` empacotados; sete são usados**.

Causa: os pacotes `@expo-google-fonts/*` têm um barril que faz `require()` de **todos** os pesos da
família. Importar um peso torna todos alcançáveis, e o Metro empacota o conjunto.

| família | empacotado | usado | morto |
|---|---|---|---|
| IBM Plex Mono | 14 arquivos · ~1,95 MB | 1 (`500Medium`) | **~1,81 MB** |
| Bricolage Grotesque | 7 arquivos · ~637 kB | 4 (400/500/600/700) | ~273 kB |
| Syne | 5 arquivos · ~346 kB | 2 (600/700) | ~208 kB |

O grosso é a IBM Plex Mono, e **ela é anterior ao redesenho** — as ondas 2–4 acrescentaram ~480 kB
de peso morto, não os 2,3 MB.

Uma boa notícia no mesmo lugar: **Fraunces e Space Grotesk não aparecem no bundle.** Continuam
instaladas como escotilha de uma linha, mas como ninguém as importa desde a onda 2, o Metro não as
alcança — a escotilha custa zero byte no aparelho. A decisão de deixá-las se pagou.

**Não conserte isso no escuro.** A saída é trocar o import do barril pelo caminho profundo
(`@expo-google-fonts/<familia>/<peso>/<Arquivo>.ttf`), e caminho errado ali não quebra o build: a
fonte simplesmente não carrega e o Android cai no padrão do sistema, calado. É mudança para fazer
**com o aparelho na mão**, na mesma sessão em que a tipografia for decidida e a Fraunces/Space
Grotesk saírem do `package.json`.
