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

module.exports = ({ config }) => {
  const doSegredo = process.env.GOOGLE_SERVICES_JSON;
  if (!doSegredo) return config;

  return {
    ...config,
    android: { ...config.android, googleServicesFile: doSegredo },
  };
};
