import assert from "node:assert/strict";
import test from "node:test";

import { ehFalhaDeRede } from "../src/offlineError.ts";

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
