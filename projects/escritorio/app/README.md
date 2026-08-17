# app — escritório (Expo / React Native, Android)

Cockpit nativo, **vidro sobre o Hermes** via BFF. L0: login single-user + captura + registro de
push. Não fala com LLM/ClickUp/GitHub direto (isso é o BFF→Hermes).

## Rodar (com o BFF já de pé)
```powershell
cd projects/escritorio/app
npm install
npx expo install --fix      # alinha as versões dos pacotes ao SDK instalado
# default do BFF em app.json → extra.bffUrl (IP da máquina, ipconfig); trocável na tela de login
npx expo start
```
No celular Android: app **Expo Go** → escaneie o QR (mesmo Wi-Fi da máquina).

A captura funciona no Expo Go. **Push remoto NÃO funciona no Expo Go** — precisa de um dev build
(ver `../development/L0-SETUP.md`, passo 4).

## Arquivos
- `App.tsx` — telas (login / captura).
- `src/api.ts` — cliente do BFF (getBffUrl/setBffUrl, login, capture, tarefas). URL do BFF
  configurável na tela de login (default em `app.json` → `extra.bffUrl`).
- `src/notifications.ts` — permissão + Expo push token.

## APK standalone (preview) — o que tira o celular da dependência do Metro

O APK instalado hoje é **dev-client**: ele não carrega bundle JS nenhum. Ou seja, o
celular só renderiza com o Metro rodando no PC (`npx expo start --dev-client`) **e** o
BFF de pé. É a explicação mais provável para o app ter parado de ser aberto.

Todo caminho documentado até aqui (`L0-SETUP.md`, `CHECKLIST-LEO.md`,
`GUIA-DETALHADO.md`) usa `--profile development`. O perfil `preview` existe no
`eas.json` desde sempre e nunca foi invocado.

**Uma vez, antes do primeiro build:**

```
eas secret:create --scope project --name GOOGLE_SERVICES_JSON \
  --type file --value ./google-services.json
```

O `google-services.json` fica fora do repo (carrega a API key AIza e o repo é
público), e o EAS faz checkout limpo — sem esse segredo o build morre no prebuild. O
`app.config.js` lê a variável que o file secret cria; sem ela, ele é inerte e o
`app.json` continua valendo sozinho.

**Depois, o build:**

```
eas build --profile preview --platform android
```

O `versionCode` sobe sozinho (`autoIncrement` no perfil preview). Isso importa menos
pelo Android — ele reinstala por cima de um versionCode igual — e mais como sinal: se
o número não muda, não dá para saber se o APK novo entrou.

**O que conferir com ele na mão** (nada disto aparece em teste ou typecheck):

1. o ícone Æ no launcher e o splash — nenhum dos dois existiu em build algum até aqui,
   porque não há diretório `android/` e os assets só entram num build novo;
2. o ícone da notificação no próximo nudge: `app.json` registra `expo-notifications`
   como string nua, sem `{icon, color}`, então o Android mascara o alpha do ícone do
   app — e o `adaptive-icon.png` é a variante opaca. Suspeita: um quadrado creme em
   cada um dos seis pushes diários;
3. que o app abre **sem** o Metro rodando. É o ponto inteiro do exercício.

`app.json` ainda fixa `bffUrl` no endereço de LAN (`192.168.0.2:8000`), então fora do
Wi-Fi de casa continua dependendo do VPS.
