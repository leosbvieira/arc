// O `google-services.json` fica FORA do repo de propósito — ele carrega a API key AIza
// do projeto Firebase e este repo é público (o motivo está escrito no `.gitignore`).
//
// Só que o EAS faz checkout limpo: o arquivo não existe na máquina de build, e o
// `app.json` aponta para ele em `android.googleServicesFile`. Resultado: `eas build`
// morre no prebuild, e era o primeiro tropeço de quem tentasse gerar o APK preview —
// justamente o passo que tira o celular da dependência do Metro.
//
// O caminho suportado é o file secret: `eas secret:create --type file` sobe o arquivo,
// e a máquina de build recebe uma variável de ambiente com o CAMINHO dele. Ler essa
// variável exige config dinâmica, e é só para isso que este arquivo existe.
//
// Comando a rodar UMA vez (do diretório do app):
//   eas secret:create --scope project --name GOOGLE_SERVICES_JSON \
//     --type file --value ./google-services.json
//
// Sem a variável — ou seja, em toda execução local — isto devolve a config intacta.
// O `app.json` continua sendo a fonte; aqui não se declara nada, só se redireciona um
// caminho quando o ambiente manda.

// Segunda responsabilidade (set/2026): o portão de https por ambiente. O perfil do
// eas.json define `EXPO_PUBLIC_APP_ENV`; em preview/production o BFF precisa ser
// https — a menos do escape `EXPO_PUBLIC_ALLOW_HTTP=1`, que o preview carrega até o
// VPS com TLS existir. Sem isto um build "de produção" nascia apontando pra LAN em
// texto claro e ninguém via. A mesma regra vale em runtime (`src/bffUrl.ts`) e no
// manifesto Android (`plugins/withCleartextTraffic.js`).
function conferirBffUrl(config) {
  const ambiente = process.env.EXPO_PUBLIC_APP_ENV;
  if (ambiente !== "preview" && ambiente !== "production") return;
  if (process.env.EXPO_PUBLIC_ALLOW_HTTP === "1") return;
  const url = process.env.EXPO_PUBLIC_BFF_URL || (config.extra && config.extra.bffUrl) || "";
  if (!/^https:\/\//i.test(url)) {
    throw new Error(
      "[app.config] perfil " + ambiente + " exige BFF https:// (recebido: \"" + (url || "vazio") + "\"). " +
        "Defina EXPO_PUBLIC_BFF_URL=https://... no perfil do eas.json, ou EXPO_PUBLIC_ALLOW_HTTP=1 enquanto o BFF estiver na LAN.",
    );
  }
}

module.exports = ({ config }) => {
  conferirBffUrl(config);

  // `EXPO_PUBLIC_BFF_URL` do perfil vence o `extra.bffUrl` do app.json (que é o
  // default de desenvolvimento na LAN).
  const bffUrl = process.env.EXPO_PUBLIC_BFF_URL;
  let saida = bffUrl ? { ...config, extra: { ...config.extra, bffUrl } } : config;

  const doSegredo = process.env.GOOGLE_SERVICES_JSON;
  if (doSegredo) {
    saida = { ...saida, android: { ...saida.android, googleServicesFile: doSegredo } };
  }
  return saida;
};
