# Briefing — proposta de redesenho visual do Aeternum (app "escritório")

Você é o diretor de design deste app. A tarefa é entregar **uma proposta visual em HTML**
que mostre como o app **deveria** ficar: mais bonito, mais intuitivo, mais fácil de usar.

---

## 1. Para quem é o app

Um único usuário: o **Leo**. O app é o centro de comando pessoal dele — não é produto de
mercado, não tem onboarding, não tem outro usuário. Ele mesmo escreveu o código.

Duas características dele definem TUDO no desenho:

**Ele é detalhista.** Incoerência visual, espaçamento errado, dois botões que fazem a
mesma coisa com nomes diferentes — isso o incomoda de verdade e faz ele parar pra
"consertar" em vez de usar. A proposta precisa ser rigorosa: um sistema, não um
apanhado de telas.

**Ele é procrastinador.** Este é o requisito mais importante do briefing.
Energia de ativação é o inimigo. Regras que decorrem disso:

- **Um toque resolve.** A ação mais frequente de cada tela tem que estar a um toque, com
  alvo grande e óbvio. Nada de "abra o menu, escolha, confirme".
- **Nada bloqueia nada.** Nunca exigir texto escrito para poder marcar um check. Escrever
  é opcional e vem *depois* do check, nunca antes.
- **O caminho certo é o mais fácil.** Em cada tela deve haver exatamente UM botão primário
  visualmente dominante. O resto é secundário e discreto.
- **Devolver algo.** Toda conclusão precisa de recompensa visível e imediata (progresso,
  selo, número que sobe, animação curta). Hoje o app termina o dia com uma linha de texto
  cinza — é o momento mais importante do dia e o mais sem graça.
- **Mostrar o que precisa de você AGORA.** Ele não deve ter que descobrir o que fazer;
  a tela diz.

---

## 2. O que é o app hoje

**Aeternum / "escritório"**: sistema de rotina pessoal. Ele captura tudo por voz ou texto
(captura universal), triagem organiza depois, tarefas e agenda, ritos de manhã (Abertura) e
de noite (Shutdown / Fechar o dia), hábitos a reduzir, rotinas recorrentes, revisão de
aprendizados (tipo Anki), e um Mentor (chat com IA que conhece o contexto dele).
Tem sistema de pontos, nível e placar (scorecard) — dimensão de jogo.

### Stack real (respeite nas recomendações)

- **React Native + Expo 54**, TypeScript. Roda no celular Android dele.
  (`react-native-web` existe, mas o alvo é celular — desenhe para o polegar.)
- Ícones: **Feather** (`@expo/vector-icons`). Use nomes de ícone que existam no Feather.
- Gradientes: `expo-linear-gradient` disponível.
- Animação: `Animated` do RN (sem reanimated instalado).
- **Não existe biblioteca de UI** — os componentes são caseiros em `app/src/ui.tsx`.

### Design system que já existe (`app/src/theme.ts` — LEIA antes de propor)

Direção declarada: **"midnight desk" (premium mono)**. Dark é o tema principal (ele é
noturno). Paleta dark: fundo `#080A0D`, cards `#15191F`, texto `#F4EFE7`, apagado `#9A9BA3`,
**accent bronze `#DEB878`**, danger `#D77969`, success `#71B49A`, info `#7D9FD0`,
lilac `#A99ACB`. Bordas são brancas quase transparentes.
Existem 10 cores de área de vida (Trabalho, Corpo, Saúde Mental, Finance, Carreira, Estudo,
Relacionamentos, Lazer, Responsabilidade, Staging).

Tipografia: **Fraunces** (serif — títulos), **Space Grotesk** (UI), **IBM Plex Mono**
(eyebrows em caixa alta com letter-spacing, e números).

**Isto é uma base boa. Não jogue fora — evolua.** Se propuser mudar um token, justifique.

### Navegação hoje

- Tabbar com 4: **Hoje · Capturar · Tarefas · Mentor**.
- **Todo o resto** (10 telas: Agenda, Abertura, Triagem, Ritmos, Reduzir, Revisão,
  Edificação, Shutdown, Fechar dia, Ajustes) mora numa **grade de 10 botões chapados
  chamada "Ferramentas"**, no fim da Home. Sem hierarquia, sem indicar o que está
  pendente, tudo do mesmo tamanho.
- Volta pelas subtelas é por um chevron no topo.

### Telas (arquivos em `app/src/screens/`)

`Home.tsx`, `Capture.tsx` (a maior, captura por voz/texto), `Tasks.tsx`, `Chat.tsx` (Mentor),
`Agenda.tsx`, `Abertura.tsx` (rito da manhã), `Shutdown.tsx`, `Fechar.tsx` (rito da noite),
`Rotinas.tsx`, `Habitos.tsx`, `Revisao.tsx`, `Edificacao.tsx`, `Triagem.tsx`, `Settings.tsx`.

**Leia as telas antes de desenhar.** Os mockups têm que mostrar os campos, estados e dados
que existem de verdade (nome dos rótulos, badges, filas, pontos) — não invente um app
genérico de produtividade.

---

## 3. Problemas conhecidos (achados de auditoria — atacar estes)

1. **O rito da noite ("Fechar o dia") é a tela de maior frequência e a pior tela do app.**
   Dois links de texto sem botão primário; até pouco tempo exigia escrever antes de marcar.
   É exatamente onde o procrastinador desiste.
2. **"Ferramentas" é uma gaveta**, não uma navegação. 10 botões iguais, nenhum diz "isto
   aqui está esperando por você".
3. **O fim do rito não devolve nada.** Zero recompensa. A única dopamina do dia é uma
   linha "✓ dia fechado".
4. **O app é bonito onde foi investido (Home, Tarefas, Mentor) e cru onde mais importa**
   (os ritos). A qualidade é desigual e ele percebe.
5. Não há sinal claro de "o que precisa de mim agora" fora da Home.

---

## 4. O que entregar

Escreva **UM arquivo**: `design/proposta-visual-kimi.html`

Requisitos do arquivo:

- **Autocontido**: um único `.html`, CSS e JS inline. Pode usar `<link>` do Google Fonts
  para Fraunces / Space Grotesk / IBM Plex Mono, **mas** declare uma pilha de fallback
  (serif/system-ui/monospace) para que fique bom mesmo offline. Nenhum outro recurso
  externo, nenhuma imagem remota — SVG inline se precisar.
- **Em português do Brasil.** Tom direto, sem marketing.
- **Tema escuro**, coerente com o "midnight desk".
- Precisa abrir bem num navegador de desktop (é lá que ele vai revisar).

Conteúdo, nesta ordem:

1. **Princípios** — 4 a 6 princípios de desenho, cada um em uma frase, cada um amarrado
   explicitamente ao "detalhista + procrastinador". Sem encher linguiça.
2. **Mockups de tela em moldura de celular** (390×844, desenhados em HTML/CSS puro — não
   screenshots, não wireframe cinza: renderize a UI proposta de verdade, com as cores e
   fontes do sistema). **Obrigatórias**:
   - **Fechar o dia** (a prioridade nº 1 — mostre como vira um toque)
   - **Home / Hoje**
   - **O substituto de "Ferramentas"** (proponha uma navegação de verdade)
   - **Abertura** (rito da manhã)
   - **Captura universal**
   - + as que você achar que merecem (Tarefas, Revisão, Mentor…)
   Ao lado/abaixo de cada mockup: um bloco curto "**o que mudou e por quê**", ligando a
   mudança ao comportamento dele.
3. **Antes → depois** para pelo menos "Fechar o dia" e "Ferramentas": mostre lado a lado o
   que existe hoje (você leu o código, então descreva com honestidade) e o proposto.
4. **Sistema**: tokens (cores, tipografia, espaçamento, raio), e os componentes que a
   proposta exige — incluindo os que ainda não existem no `ui.tsx` (ex.: botão primário
   grande de rito, cartão de pendência, selo de recompensa, estado de conclusão).
   Mostre cada componente renderizado, não só descrito.
5. **Plano de implementação em ondas**: o que fazer primeiro para o maior ganho com o menor
   custo, ordenado. Seja concreto: nome de arquivo e o que muda nele.

Também escreva `design/NOTAS-KIMI.md`: um resumo curto (máx. 1 página) das decisões e das
dúvidas que sobraram.

---

## 5. Restrições duras (não viole)

- **NÃO modifique NENHUM arquivo fora de `design/`.** Outro agente está editando
  `app/` neste exato momento — qualquer escrita lá causa conflito real.
  Tudo fora de `design/` é **somente leitura**.
- **Não rode** `npm`, `expo`, `git`, testes, nem instale nada. Só ler e escrever em `design/`.
- Não crie subpastas dentro de `design/`; só os dois arquivos pedidos.
- Não faça perguntas — decida e justifique dentro do próprio HTML.

## 6. Barra de qualidade

Ele é detalhista: uma proposta genérica de dashboard SaaS será rejeitada. O que se espera é
uma peça de design com ponto de vista, que pareça feita **para este app e para esta pessoa**,
com alinhamento, ritmo tipográfico e espaçamento impecáveis. Densidade alta de conteúdo
real, densidade zero de placeholder. Se um mockup ficar bonito mas não reduzir a energia de
ativação dele, está errado.
