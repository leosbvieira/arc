// O app abria a tabbar com token morto porque `!!t` pergunta se o token EXISTE,
// não se ele vale. Com TTL de 30 dias isso é um evento mensal, não um acidente.
import assert from "node:assert/strict";
import test from "node:test";

import {
  MARGEM_MS,
  decodeBase64Url,
  expiracaoDoToken,
  sessaoValida,
} from "../src/sessao.ts";

/** Monta um JWT de mentira: só o payload importa, a assinatura nunca é lida aqui. */
function tokenCom(payload) {
  const b64 = (o) =>
    Buffer.from(JSON.stringify(o))
      .toString("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  return `${b64({ alg: "HS256", typ: "JWT" })}.${b64(payload)}.assinatura-falsa`;
}

const AGORA = Date.UTC(2026, 7, 16, 12, 0, 0);

test("token vencido não autentica", () => {
  const ontem = tokenCom({ exp: Math.floor(AGORA / 1000) - 86400 });
  assert.equal(sessaoValida(ontem, AGORA), false);
});

test("token válido autentica", () => {
  const semanaQueVem = tokenCom({ exp: Math.floor(AGORA / 1000) + 7 * 86400 });
  assert.equal(sessaoValida(semanaQueVem, AGORA), true);
});

test("o dia 31 do TTL de 720h é o caso real", () => {
  const emitido = AGORA - 31 * 86400 * 1000;
  const exp = Math.floor((emitido + 720 * 3600 * 1000) / 1000); // 30 dias após emitir
  assert.equal(sessaoValida(tokenCom({ exp }), AGORA), false);
});

test("token que morre em segundos não serve pra abrir o app", () => {
  // Sem margem, ele passaria no boot e produziria exatamente a tela de 401 que
  // esta checagem existe pra evitar.
  const quase = tokenCom({ exp: Math.floor((AGORA + MARGEM_MS / 2) / 1000) });
  assert.equal(sessaoValida(quase, AGORA), false);

  const folgado = tokenCom({ exp: Math.floor((AGORA + MARGEM_MS * 3) / 1000) });
  assert.equal(sessaoValida(folgado, AGORA), true);
});

test("sem token não há sessão", () => {
  assert.equal(sessaoValida(null, AGORA), false);
  assert.equal(sessaoValida(undefined, AGORA), false);
  assert.equal(sessaoValida("", AGORA), false);
});

test("token ilegível é tratado como VÁLIDO — quem decide é o servidor", () => {
  // Deslogar por não conseguir ler seria pior que deixar o 401 aparecer: erraria
  // contra o Leo em cima de um palpite nosso sobre o formato.
  assert.equal(sessaoValida("nao-e-jwt", AGORA), true);
  assert.equal(sessaoValida("a.b.c", AGORA), true);
  assert.equal(sessaoValida(tokenCom({ sem_exp: 1 }), AGORA), true);
  assert.equal(sessaoValida(tokenCom({ exp: "amanhã" }), AGORA), true);
});

test("expiracaoDoToken devolve milissegundos, não segundos", () => {
  const exp = Math.floor(AGORA / 1000) + 100;
  assert.equal(expiracaoDoToken(tokenCom({ exp })), exp * 1000);
  assert.equal(expiracaoDoToken(null), null);
  assert.equal(expiracaoDoToken("a.b.c"), null);
});

test("o decoder devolve UTF-8 de verdade, não os bytes crus", () => {
  // A primeira versão deste teste usava `sub: "leo"` — 100% ASCII — e por isso
  // passava mesmo com o decoder devolvendo latin1: "leó" virava "leÃ³" e ninguém
  // notava. Uma revisão hostil pegou. Agora o assert é sobre o que o nome promete.
  const exp = Math.floor(AGORA / 1000) + 100;
  const payload = { exp, sub: "João — ação 東 🔥" };
  const t = tokenCom(payload);
  assert.equal(expiracaoDoToken(t), exp * 1000);

  const cru = decodeBase64Url(t.split(".")[1]);
  assert.equal(JSON.parse(cru).sub, payload.sub);
});

test("payload malformado não derruba o boot", () => {
  assert.equal(decodeBase64Url("!!!"), null);
  assert.equal(expiracaoDoToken("a.!!!.c"), null);
  // Continuação UTF-8 solta: bytes inválidos viram null, não exceção.
  assert.equal(decodeBase64Url("gA"), null);
});
