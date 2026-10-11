// Validação do endereço do BFF — módulo PURO (sem expo), testável em `node --test`.
//
// Por que existe: `setBffUrl` aceitava qualquer string e `getBffUrl` devolvia o que
// estivesse salvo no SecureStore sem olhar. Um override digitado errado (ou um
// `http://` num build que deveria falar só https) virava comportamento silencioso:
// cada request falhava com "sem conexão" e ninguém sabia por quê.
//
// Regra de esquema: https sempre; http SÓ no ambiente `development`, ou com o
// escape explícito `EXPO_PUBLIC_ALLOW_HTTP=1` (o APK preview de hoje fala com o BFF
// na LAN do PC em texto claro — o escape fica no perfil `preview` do eas.json até o
// VPS com TLS subir, e sai de lá junto com esta frase).

export type AppEnv = "development" | "preview" | "production";

export function ambienteDoApp(raw: string | undefined = process.env.EXPO_PUBLIC_APP_ENV): AppEnv {
  if (raw === "preview" || raw === "production") return raw;
  // Sem variável (Metro local, `expo start`) = desenvolvimento.
  return "development";
}

export function httpPermitido(
  ambiente: AppEnv = ambienteDoApp(),
  allowHttp: string | undefined = process.env.EXPO_PUBLIC_ALLOW_HTTP,
): boolean {
  return ambiente === "development" || allowHttp === "1";
}

export class BffUrlInvalida extends Error {}

/** Normaliza (trim, sem barra final) e valida. Lança `BffUrlInvalida` com mensagem
 *  em português pronta pra tela. */
export function validarBffUrl(entrada: string, permitirHttp: boolean = httpPermitido()): string {
  const bruta = (entrada ?? "").trim();
  if (!bruta) throw new BffUrlInvalida("informe o endereço do servidor");
  let u: URL;
  try {
    u = new URL(bruta);
  } catch {
    throw new BffUrlInvalida("endereço inválido — use o formato https://host:porta");
  }
  if (u.protocol !== "https:" && u.protocol !== "http:") {
    throw new BffUrlInvalida("o endereço precisa começar com https:// (ou http:// em desenvolvimento)");
  }
  if (u.protocol === "http:" && !permitirHttp) {
    throw new BffUrlInvalida("neste build o servidor precisa ser https://");
  }
  if (!u.hostname) throw new BffUrlInvalida("endereço sem host");
  if (u.username || u.password) throw new BffUrlInvalida("não coloque usuário/senha no endereço");
  if (u.search || u.hash) throw new BffUrlInvalida("o endereço não deve ter ? nem #");
  // `URL` já normaliza host/porta; só tiramos barras finais do caminho.
  const caminho = u.pathname.replace(/\/+$/, "");
  return `${u.protocol}//${u.host}${caminho}`;
}

/** Versão que não lança: `null` quando inválida. Para o que já está salvo no
 *  aparelho — um override ruim é ignorado, não derruba o boot. */
export function bffUrlValidaOuNull(entrada: string | null | undefined, permitirHttp?: boolean): string | null {
  if (!entrada) return null;
  try {
    return validarBffUrl(entrada, permitirHttp);
  } catch {
    return null;
  }
}
