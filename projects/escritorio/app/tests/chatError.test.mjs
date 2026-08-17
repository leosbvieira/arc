import assert from "node:assert/strict";
import test from "node:test";

import { mensagemDaFalhaDoChat, segundosDoRetryAfter } from "../src/chatError.ts";

const falha = (status, detail, retryAposS = null) => ({ status, detail, retryAposS });

test("cota esgotada diz quando volta, e não pede ação nenhuma", () => {
  const msg = mensagemDaFalhaDoChat(falha(503, "hermes_quota", 120));
  assert.match(msg, /cota do modelo acabou/);
  assert.match(msg, /~2 min/);
});

test("arredonda o retry para cima — 90s não pode virar '1 min'", () => {
  // Dizer 1 min faz ele tentar aos 60s, falhar de novo, e desconfiar do sistema.
  assert.match(mensagemDaFalhaDoChat(falha(503, "hermes_quota", 90)), /~2 min/);
});

test("retry curto vira 'menos de 1 min' em vez de '~1 min'", () => {
  assert.match(mensagemDaFalhaDoChat(falha(503, "hermes_quota", 30)), /menos de 1 min/);
});

test("cota sem Retry-After ainda diz que é cota", () => {
  // O Hermes só calcula os segundos quando o provedor os manda.
  const msg = mensagemDaFalhaDoChat(falha(503, "hermes_quota", null));
  assert.match(msg, /cota do modelo acabou/);
  assert.match(msg, /daqui a pouco/);
});

test("credencial consumida é a ÚNICA que manda ele fazer algo", () => {
  const msg = mensagemDaFalhaDoChat(falha(503, "hermes_credencial"));
  assert.match(msg, /codex/);
  assert.match(msg, /hermes auth/);
});

test("hermes indisponível aponta o PC — a causa mais provável", () => {
  assert.match(mensagemDaFalhaDoChat(falha(502, "hermes_indisponivel")), /PC pode estar desligado/);
});

test("código desconhecido não vira frase inventada", () => {
  // Um detail novo do BFF não pode ser explicado errado com confiança.
  assert.match(mensagemDaFalhaDoChat(falha(500, "coisa_nova")), /erro 500/);
  assert.match(mensagemDaFalhaDoChat(falha(401, null)), /erro 401/);
});

test("Retry-After só aceita a forma delta-seconds", () => {
  assert.equal(segundosDoRetryAfter("120"), 120);
  assert.equal(segundosDoRetryAfter(" 60 "), 60);
  assert.equal(segundosDoRetryAfter(null), null);
  assert.equal(segundosDoRetryAfter("Wed, 21 Oct 2026 07:28:00 GMT"), null);
  assert.equal(segundosDoRetryAfter("-5"), null);
  assert.equal(segundosDoRetryAfter("1.5"), null);
  assert.equal(segundosDoRetryAfter(""), null);
});


test("ocupado não é o mesmo que fora do ar", () => {
  // O slot do Hermes é UM só, compartilhado por chat, captura, triagem, leitura,
  // anki, diário e review. Trabalho de fundo segurando a vez não é defeito — e cair
  // no genérico "erro 503" mandava o Leo caçar problema que não existe.
  const msg = mensagemDaFalhaDoChat({
    status: 503,
    detail: "hermes_ocupado",
    retryAposS: 60,
  });
  assert.match(msg, /terminando outra tarefa/);
  assert.ok(!msg.includes("503"), `código cru vazou pra bolha: ${msg}`);
  assert.ok(!msg.includes("desligado"), "ocupado não é PC desligado");
});

test("ocupado sem Retry-After ainda diz o que fazer", () => {
  const msg = mensagemDaFalhaDoChat({ status: 503, detail: "hermes_ocupado", retryAposS: null });
  assert.match(msg, /Tenta de novo daqui a pouco/);
});
