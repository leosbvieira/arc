import assert from "node:assert/strict";
import test from "node:test";

import { PrazoEsgotado, comPrazo, comPrazoAbortavel } from "../src/prazo.ts";

test("resolve antes do prazo: passa o valor", async () => {
  assert.equal(await comPrazo(Promise.resolve(7), 50, "x"), 7);
});

test("rejeita antes do prazo: passa o erro original", async () => {
  await assert.rejects(comPrazo(Promise.reject(new Error("erro 401")), 50, "x"), /401/);
});

test("sem resposta: PrazoEsgotado com o rótulo", async () => {
  const pendente = new Promise(() => {});
  await assert.rejects(comPrazo(pendente, 10, "remover push"), (e) => {
    assert.ok(e instanceof PrazoEsgotado);
    assert.match(e.message, /remover push: sem resposta em 10ms/);
    return true;
  });
});

test("comPrazoAbortavel: vencido o prazo, o signal é abortado", async () => {
  let sinal;
  await assert.rejects(
    comPrazoAbortavel((signal) => {
      sinal = signal;
      return new Promise(() => {});
    }, 10, "registrar push"),
    PrazoEsgotado,
  );
  assert.equal(sinal.aborted, true);
});

test("comPrazoAbortavel: resolveu a tempo, o signal fica intacto", async () => {
  let sinal;
  assert.equal(await comPrazoAbortavel(async (signal) => { sinal = signal; return 1; }, 50, "x"), 1);
  assert.equal(sinal.aborted, false);
});
