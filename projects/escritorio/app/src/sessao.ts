// O app decidia estar autenticado porque o token EXISTIA, nunca porque ele valia.
//
// `jwt_ttl_hours=720`: o token dura 30 dias, então o vencimento é evento MENSAL
// marcado no calendário, não acidente raro. No dia 31 o app abria direto na tabbar
// com um token morto — a Home dizia "alguns dados não responderam", Tarefas, Fechar
// e Shutdown diziam "erro 401", o Mentor dizia "Não consegui responder agora (erro
// 401)" — e nada levava de volta ao login. A cura era adivinhar que Ajustes → Sair
// resolvia. O `logout.ts` já existe por causa da MESMA data de vencimento.
//
// A checagem é local e offline de propósito: a validade não depende do servidor
// estar de pé, e no avião a resposta certa continua sendo "sua sessão venceu", não
// "não consegui perguntar". A assinatura NÃO é verificada aqui — isso é trabalho do
// servidor, e um token adulterado morre no `require_auth` de qualquer jeito. Aqui só
// se lê a data que o próprio servidor carimbou.
//
// Módulo sem import nenhum (nem de valor, nem de tipo) porque é isso que permite
// rodá-lo no `node --test`: `atob` também fica de fora, que o Hermes nem sempre traz.

const B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

/** base64url -> texto. Sem `atob`, sem `Buffer`: os dois faltam em algum dos dois
 * runtimes onde este código roda (Hermes no aparelho, node no teste). */
function decodeBase64Url(entrada: string): string | null {
  const limpa = entrada.replace(/=+$/, "");
  let bits = 0;
  let acc = 0;
  let saida = "";
  for (const ch of limpa) {
    const v = B64.indexOf(ch);
    if (v < 0) return null;
    acc = (acc << 6) | v;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      saida += String.fromCharCode((acc >> bits) & 0xff);
    }
  }
  return saida;
}

/** `exp` do JWT em MILISSEGUNDOS, ou null se o token não disser. */
export function expiracaoDoToken(token: string | null | undefined): number | null {
  if (!token) return null;
  const partes = token.split(".");
  if (partes.length !== 3) return null;
  const payload = decodeBase64Url(partes[1]);
  if (!payload) return null;
  try {
    const dados = JSON.parse(payload) as { exp?: unknown };
    return typeof dados.exp === "number" && Number.isFinite(dados.exp)
      ? dados.exp * 1000
      : null;
  } catch {
    return null;
  }
}

/** Margem antes do vencimento: um token que morre em 30 segundos não serve pra
 * abrir o app — só produz a tela de erro que este módulo existe pra evitar. */
export const MARGEM_MS = 60_000;

export function sessaoValida(
  token: string | null | undefined,
  agoraMs: number,
): boolean {
  if (!token) return false;
  const exp = expiracaoDoToken(token);
  // Token sem `exp` legível é tratado como VÁLIDO: o servidor é quem decide, e
  // deslogar por não saber ler seria pior que deixar o 401 aparecer. O caso que
  // importa — o vencimento mensal — sempre traz `exp`.
  if (exp === null) return true;
  return exp - MARGEM_MS > agoraMs;
}
