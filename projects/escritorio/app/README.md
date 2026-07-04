# app — escritório (Expo / React Native, Android)

Cockpit nativo, **vidro sobre o Hermes** via BFF. L0: login single-user + captura + registro de
push. Não fala com LLM/ClickUp/GitHub direto (isso é o BFF→Hermes).

## Rodar (com o BFF já de pé)
```powershell
cd projects/escritorio/app
npm install
npx expo install --fix      # alinha as versões dos pacotes ao SDK instalado
# edite src/api.ts → BFF_URL com o IP da sua máquina (ipconfig)
npx expo start
```
No celular Android: app **Expo Go** → escaneie o QR (mesmo Wi-Fi da máquina).

A captura funciona no Expo Go. **Push remoto NÃO funciona no Expo Go** — precisa de um dev build
(ver `../development/L0-SETUP.md`, passo 4).

## Arquivos
- `App.tsx` — telas (login / captura).
- `src/api.ts` — cliente do BFF (login, capture, registerDevice). **BFF_URL aqui.**
- `src/notifications.ts` — permissão + Expo push token.
