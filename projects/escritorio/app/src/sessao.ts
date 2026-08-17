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

/** base64url -> texto UTF-8. Sem `atob`, sem `Buffer`, sem `TextDecoder`: os três
 * faltam em algum dos dois runtimes onde este código roda (Hermes no aparelho, node
 * no teste).
 *
 * O UTF-8 é decodificado de verdade, e não só os bytes. A primeira versão devolvia
 * latin1 — `exp` é número e sobrevivia, então nada quebrava HOJE, mas qualquer campo
 * de texto lido daqui viria como mojibake ("leó" virava "leÃ³"), esperando o primeiro
 * leitor futuro. Bug latente é dívida com juros. */
export function decodeBase64Url(entrada: string): string | null {
  const limpa = entrada.replace(/=+$/, "");
  const bytes: number[] = [];
  let bits = 0;
  let acc = 0;
  for (const ch of limpa) {
    const v = B64.indexOf(ch);
    if (v < 0) return null;
    acc = (acc << 6) | v;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      bytes.push((acc >> bits) & 0xff);
    }
  }

  let saida = "";
  for (let i = 0; i < bytes.length; ) {
    const b = bytes[i];
    let ponto: number;
    let extras: number;
    if (b < 0x80) {
      ponto = b;
      extras = 0;
    } else if ((b & 0xe0) === 0xc0) {
      ponto = b & 0x1f;
      extras = 1;
    } else if ((b & 0xf0) === 0xe0) {
      ponto = b & 0x0f;
      extras = 2;
    } else if ((b & 0xf8) === 0xf0) {
      ponto = b & 0x07;
      extras = 3;
    } else {
      return null;
    }
    if (i + extras >= bytes.length) return null; // sequência truncada
    for (let j = 1; j <= extras; j++) {
      const seguinte = bytes[i + j];
      if ((seguinte & 0xc0) !== 0x80) return null;
      ponto = (ponto << 6) | (seguinte & 0x3f);
    }
    saida += String.fromCodePoint(ponto);
    i += extras + 1;
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
