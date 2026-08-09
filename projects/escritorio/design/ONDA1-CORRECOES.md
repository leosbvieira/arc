# Encargo — correções da Onda 1

A Onda 1 passou por revisão. O escopo, o TDD e os testes estão bons, e nenhuma correção de bug
antiga foi regredida. Sobraram **dois defeitos confirmados**. Conserte os dois, nada além.

---

## Defeito 1 — o rótulo do BigAction estoura a largura da tela

**Onde:** `app/src/ui.tsx` (estilo `bigact` e os dois `<Text>` do BigAction).

**O que acontece:** o título e o sub ficam lado a lado numa `row` sem `flexShrink` nem
`numberOfLines`. No CSS do mockup isso não aparece porque `flex-shrink` tem padrão 1; **no Yoga o
padrão é 0**, então nenhum dos dois encolhe e o sub vaza para fora do botão.

Medição feita na revisão, com as métricas reais dos `.ttf` em `node_modules/@expo-google-fonts`:

- "Fechar o dia" @15.5 SpaceGrotesk_600SemiBold = **91,3dp**
- "garante +80 · bônus até +140" @10.5 IBMPlexMono_500Medium (letterSpacing 0.4) = **187,6dp**
- \+ gap 10 = **288,9dp**
- Espaço útil num aparelho de 360dp: 360 − 16 (padding do `content` no App) − 16 (padding do
  ScrollView do Fechar) ×2 lados − 36 (paddingHorizontal do bigact) = **260dp**

Estouro de ~29dp, e **é o estado padrão ao abrir a tela**, não caso de borda. A variante
"garante +120 · bônus até +140" (29 chars) estoura até em 390pt.

**Correção:** `flexShrink: 1` no estilo do sub e `numberOfLines={1}` no `<Text>` do sub. Confira se
o título também precisa de `flexShrink` quando o sub for curto. Se sobrar risco com `fontScale`
grande (o `allowFontScaling` está ligado por padrão), diga na resposta — não invente solução
maior que o problema.

---

## Defeito 2 — a promessa encolhe quando o Leo obedece

**Onde:** `app/src/closingPoints.ts`, seus testes, e o ponto em `app/src/screens/Fechar.tsx` que
fixa o número da recompensa.

**O que acontece hoje:** `teto` conta as rotinas **não marcadas**, mas `garantido` nunca as absorve
quando elas são marcadas. Com 1 rotina aberta e sem texto o botão diz "garante +80 · bônus até
+140"; o Leo marca a rotina e escreve, e o botão passa a dizer "garante +120". **O teto caiu**, e
+140 é inalcançável por qualquer caminho. Os pontos das rotinas que a própria tela creditou não
aparecem no total.

**A correção decidida pelo Leo** — as duas grandezas viram a mesma família, em função do dia
inteiro:

- **garantido** = o que ele leva **se fechar agora**
  `fechamento + (marcadas × rotina) + (temTexto ? despejoBonus : 0)`
- **teto** = o máximo **do dia**, constante enquanto ele trabalha
  `fechamento + (total de rotinas do dia × rotina) + despejoBonus`
- **o herói da RewardSheet** = o `garantido` no instante do toque (já é assim; muda só a fórmula).

Assim o número **sobe** conforme ele marca, o teto **não se move**, e quando ele marca tudo e
escreve, `garantido === teto` — o rótulo colapsa para a forma curta que já existe ("garante +N").

**Casos de aceite** (o primeiro é o do mockup):

| estado | rótulo esperado |
|---|---|
| 1 rotina no dia, 0 marcadas, sem texto | `garante +80 · bônus até +140` |
| 1 rotina no dia, 1 marcada, com texto | `garante +140` |
| 5 rotinas, 4 marcadas de manhã, sem texto | `garante +160 · bônus até +220` |
| 5 rotinas, 5 marcadas, com texto | `garante +220` |
| 0 rotinas no dia, sem texto | `garante +80 · bônus até +120` |

**A assinatura das funções muda** (hoje recebem "não marcadas"; passam a precisar de marcadas e do
total). Ajuste as chamadas em `Fechar.tsx`.

### TDD, de novo

Os testes atuais **prendem a fórmula antiga** — eles vão falhar, e isso é correto: é mudança de
especificação, não bug de teste. O procedimento:

1. **Primeiro** reescreva/adicione os testes para a fórmula nova, incluindo os cinco casos de
   aceite acima. Rode e **veja falhar**.
2. Só então mude `closingPoints.ts`.
3. Rode tudo de novo.

Não apague testes para fazer a suíte passar. Se um teste antigo virou obsoleto, reescreva-o para a
regra nova e mantenha a intenção que ele documentava.

---

## Contexto que NÃO é para consertar agora

A revisão confirmou que o BFF paga `pontos_por_rotina = 1` (`bff/app/config.py:73`) e **zero pelo
fechamento** (`bff/app/pontos.py:195`), então a tabela `POINTS` é ficção declarada. O Leo decidiu
alinhar isso numa **onda própria, depois**. Não toque em `bff/`, e não mude os valores de `POINTS`.

## Restrições

- Só estes arquivos: `app/src/ui.tsx`, `app/src/closingPoints.ts`,
  `app/tests/closingPoints.test.mjs`, `app/src/screens/Fechar.tsx`.
- Nada de `git`, nada de `npm install`.
- **Não delegue para subagentes.**
- Antes de devolver o turno, rode `npm run typecheck` e `npm test` em `projects/escritorio/app` e
  cole a saída real dos dois na resposta.
