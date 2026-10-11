import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_TENTATIVAS,
  decidirAposFalha,
  ehFalhaDeRede,
  mensagemDaRecusa,
  paraAFila,
  statusDoErro,
} from "../src/offlineError.ts";

test("fetch que nem saiu do aparelho é falha de rede", () => {
  assert.equal(ehFalhaDeRede(new TypeError("Network request failed")), true);
  assert.equal(ehFalhaDeRede(new TypeError("Failed to fetch")), true);
});

test("timeout do lado do cliente conta como sem rede", () => {
  const abort = new Error("Aborted");
  abort.name = "AbortError";
  assert.equal(ehFalhaDeRede(abort), true);
});

test("404 NÃO é falha de rede — a tarefa não existe, reenviar não conserta", () => {
  assert.equal(ehFalhaDeRede(new Error("erro 404")), false);
});

test("401 NÃO é falha de rede — sessão expirada, precisa de login", () => {
  assert.equal(ehFalhaDeRede(new Error("erro 401")), false);
});

test("500 NÃO entra na fila: o servidor RECEBEU e falhou", () => {
  // Reenviar às cegas poderia concluir duas vezes. É erro para mostrar, não para engolir.
  assert.equal(ehFalhaDeRede(new Error("erro 500")), false);
});

test("erro desconhecido não vira fila silenciosa", () => {
  assert.equal(ehFalhaDeRede(new Error("qualquer coisa")), false);
  assert.equal(ehFalhaDeRede(null), false);
  assert.equal(ehFalhaDeRede(undefined), false);
  assert.equal(ehFalhaDeRede("string solta"), false);
});

// --- a decisão da fila -----------------------------------------------------
// A fila parava no PRIMEIRO erro, qualquer erro, e o item recusado ficava na
// cabeça pra sempre segurando tudo que entrou depois.

const semRede = () => new TypeError("Network request failed");
const abortado = () => {
  const e = new Error("Aborted");
  e.name = "AbortError";
  return e;
};
const doServidor = (status) => new Error(`erro ${status}`);

test("falha de rede espera, e NÃO gasta tentativa", () => {
  assert.equal(decidirAposFalha(semRede(), 1), "esperar_rede");
  // Mesmo muito acima do limite: uma semana offline não pode aposentar a fila.
  assert.equal(decidirAposFalha(semRede(), MAX_TENTATIVAS + 5), "esperar_rede");
  assert.equal(decidirAposFalha(abortado(), 1), "esperar_rede");
});

test("401 é da sessão, não do item — para a fila inteira", () => {
  assert.equal(decidirAposFalha(doServidor(401), 1), "esperar_login");
  assert.equal(decidirAposFalha(doServidor(401), MAX_TENTATIVAS + 5), "esperar_login");
});

test("o 404 eterno vai pro fim da fila em vez de travá-la", () => {
  // Este é o bug: antes, o `catch { break }` deixava este item na cabeça pra sempre.
  assert.equal(decidirAposFalha(doServidor(404), 1), "recolocar_no_fim");
});

test("depois de MAX_TENTATIVAS o item sai da fila", () => {
  assert.equal(decidirAposFalha(doServidor(404), MAX_TENTATIVAS - 1), "recolocar_no_fim");
  assert.equal(decidirAposFalha(doServidor(404), MAX_TENTATIVAS), "desistir");
  assert.equal(decidirAposFalha(doServidor(500), MAX_TENTATIVAS + 1), "desistir");
});

test("só rede e login param a drenagem", () => {
  assert.equal(paraAFila("esperar_rede"), true);
  assert.equal(paraAFila("esperar_login"), true);
  assert.equal(paraAFila("recolocar_no_fim"), false);
  assert.equal(paraAFila("desistir"), false);
});

test("statusDoErro lê o contrato do api.ts, e só ele", () => {
  assert.equal(statusDoErro(doServidor(404)), 404);
  assert.equal(statusDoErro(doServidor(500)), 500);
  assert.equal(statusDoErro(semRede()), null);
  assert.equal(statusDoErro(new Error("erro de rede")), null);
  assert.equal(statusDoErro("erro 404"), null); // string não é Error
  assert.equal(statusDoErro(null), null);
});

test("erro desconhecido é recusa, não queda de rede", () => {
  // Conservador de propósito: chamar de "sem conexão" o que não era foi o defeito.
  assert.equal(decidirAposFalha(new Error("qualquer outra coisa"), 1), "recolocar_no_fim");
});

test("a mensagem da recusa nunca culpa a rede e sempre diz o que fazer", () => {
  for (const erro of [doServidor(401), doServidor(404), doServidor(500), doServidor(502),
                      new Error("qualquer outra coisa")]) {
    const msg = mensagemDaRecusa(erro);
    assert.ok(msg.length > 0);
    assert.ok(!msg.includes("sem conexão"), `havia conexão: ${msg}`);
  }
  assert.match(mensagemDaRecusa(doServidor(401)), /entre de novo/);
  assert.match(mensagemDaRecusa(doServidor(500)), /recebeu e falhou/);
  assert.match(mensagemDaRecusa(doServidor(404)), /404/);
});

test("409 (client_key com outro conteúdo) desiste na primeira: reenviar nunca muda a resposta", () => {
  assert.equal(decidirAposFalha(doServidor(409), 1), "desistir");
});
