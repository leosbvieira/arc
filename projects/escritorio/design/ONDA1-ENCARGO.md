# Encargo — Onda 1 (implementação)

A proposta `proposta-c2-sobria.html` foi **aprovada pelo Leo**. Esta é a implementação da **onda 1**,
e só dela. É código de produção no app dele, não mais proposta.

## Escopo — exatamente estes arquivos

| arquivo | o que fazer |
|---|---|
| `app/src/theme.ts` | Adicionar `faint: "#5F626B"` (e o equivalente claro) ao tipo `Palette` **e às duas paletas** `dark` e `light` — o tipo exige as duas. Adicionar a tabela `POINTS`, comentada como provisória e display-only. |
| `app/src/<novo>.ts` | Módulo **puro** com a regra de pontos do fechamento (ver TDD abaixo). Sem import de `react-native`. |
| `app/tests/<novo>.test.mjs` | O teste do módulo acima. |
| `app/src/ui.tsx` | Criar `BigAction`, `QuestRow`, `SegmentBar`, `RewardSheet`. `Animated` puro (reanimated **não** está instalado). |
| `app/src/screens/Fechar.tsx` | Os dois links de texto viram `BigAction`; as rotinas viram `QuestRow`; o estado `done` vira `RewardSheet`. |

**Não toque em mais nada.** Em particular: nada em `bff/`, nada em `App.tsx`, e nada nas telas
`Home.tsx` / `Tasks.tsx` / `Revisao.tsx` — elas são ondas 2 e 3. Não faça commit.

`POINTS`, conforme a proposta:
`{ tarefa: 10, rotina: 20, captura: 5, fechamento: 80, despejoBonus: 40 }`

## TDD — obrigatório, e é o que vou revisar primeiro

O repositório já tem o padrão: lógica pura em `src/*.ts` (ex.: `closingChecks.ts`, `taskDue.ts`,
`homeAction.ts`), testada por `tests/*.test.mjs` com `node --test`. O Node 24 tira os tipos sozinho,
então o teste importa o `.ts` direto (`import { x } from "../src/x.ts"`). Telas `.tsx` não são
testadas — por isso a regra abaixo.

**Extraia a regra de pontos para um módulo puro e faça TDD nela:**

1. **RED primeiro.** Escreva o teste, rode, e **veja falhar**. Não escreva a implementação antes.
2. **GREEN.** Código mínimo para passar.
3. Rode a suíte inteira.

A regra a implementar é o rótulo do `BigAction` — `"garante +80 · bônus até +140"` no mockup:

- **garantido** = o que o toque no botão registra agora = `POINTS.fechamento` + (se já há texto
  escrito) `POINTS.despejoBonus`.
- **teto** = garantido + (rotinas ainda não marcadas × `POINTS.rotina`) + (se ainda não há texto)
  `POINTS.despejoBonus`.
- Quando **teto === garantido** (nada mais a ganhar), o rótulo mostra só `"garante +N"`, sem a
  parte de bônus. Este caso está no mockup da galeria de componentes.

Confira contra o mockup: nenhum texto escrito e **uma** rotina não marcada → `garante +80 ·
bônus até +140`. Se sua fórmula não bater com isso, a fórmula está errada.

Cubra também: tudo marcado e sem texto; tudo marcado e com texto; zero rotinas no dia.

## Fidelidade ao desenho aprovado (é aqui que se perde)

- **O botão está sempre habilitado.** A única condição de bloqueio é a real de erro, que já existe
  no arquivo: `routinesUnavailable`. **Escrever nunca é portão** — o despejo vira bônus opcional
  abaixo do botão, e o "estruturar com o Hermes" continua existindo, como caminho secundário.
- **Ponto em repouso é metadado**: mono ~10px, tom `faint`, alinhado à direita. Marcado, sobe um
  degrau para sálvia (`colors.success`). **Nunca bronze, nunca pill, nunca fundo.**
- **Um bronze cheio por tela** — o `BigAction`. A exceção declarada é a tela de recompensa.
- **Checkbox quadrado**, 24px, canto ~7px (o Leo pediu quadrado; canto vivo destoaria do sistema).
- **Sem streak.** O BFF não expõe sequência corrida. A `RewardSheet` nasce sem essa linha —
  **nenhum número inventado**. Ela usa o que `getPontos()` já traz: saldo, nível, ciclo.
- **Desconto em muted, nunca coral** (a lei do `Revisao.tsx`: desconto não é erro, é fato).
- Animações com `Animated`, **abaixo de 400ms**.
- **Tipografia não muda nesta onda.** A troca para Bricolage/Syne é a onda 2. Use as fontes atuais.

## Não regrida o que já foi consertado

`Fechar.tsx` carrega correções de bugs reais nos comentários. Leia-os antes de reescrever, e
preserve o comportamento:

- marcar é **otimista e imediato** (`checkRoutine` no toque), com rollback em falha;
- o estado do servidor semeia, mas **decisão já tomada na tela vence** (`seedDecisions`), e rotina
  sem decisão fica **fora** do objeto — ausência não é furo; foi isso que já apagou a manhã uma vez;
- lista vazia é legítima; o que trava é **falha de carregamento**, não zero rotinas;
- o seletor de template só aparece como fallback quando o dia não foi marcado de manhã;
- o retry de rotinas continua existindo.

Se um comentário existente explicar um bug, **mantenha o comentário**.

## Verificação (obrigatória antes de devolver o turno)

Rode, de dentro de `projects/escritorio/app`:

```
npm run typecheck
npm test
```

As duas têm que passar, incluindo os testes que já existiam. `npm install` **não** é permitido.
Se algo quebrar, conserte — não deixe para o revisor.

## Restrições

- **Não delegue para subagentes**: no modo `-p` o processo morre quando você devolve o turno.
- Nada de `git` (nem `add`, nem `commit`, nem `checkout`).
- Não faça perguntas: decida e siga, e explique as decisões na resposta final.

Na resposta final, liste: os arquivos tocados, o teste que escreveu, **a saída real** de
`npm run typecheck` e `npm test`, e qualquer ponto onde você divergiu do desenho e por quê.
