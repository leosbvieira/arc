const { AndroidConfig, withAndroidManifest } = require("@expo/config-plugins");

// `usesCleartextTraffic` (HTTP sem TLS) só entra no manifesto quando o build pode
// falar http: ambiente `development` (Metro local, sem variável) ou o escape
// explícito `EXPO_PUBLIC_ALLOW_HTTP=1` — que hoje o perfil `preview` do eas.json
// carrega porque o BFF ainda está na LAN do PC. Antes era incondicional: um APK de
// produção aceitaria http pra sempre. A mesma regra vale em runtime (`src/bffUrl.ts`).
function httpPermitido(env = process.env) {
  const ambiente = env.EXPO_PUBLIC_APP_ENV;
  const dev = ambiente !== "preview" && ambiente !== "production";
  return dev || env.EXPO_PUBLIC_ALLOW_HTTP === "1";
}

module.exports = function withCleartextTraffic(config) {
  return withAndroidManifest(config, (androidConfig) => {
    const application = AndroidConfig.Manifest.getMainApplicationOrThrow(
      androidConfig.modResults,
    );
    if (httpPermitido()) {
      application.$["android:usesCleartextTraffic"] = "true";
    } else {
      delete application.$["android:usesCleartextTraffic"];
    }
    return androidConfig;
  });
};

module.exports.httpPermitido = httpPermitido;
