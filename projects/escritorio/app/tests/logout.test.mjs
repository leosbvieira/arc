import assert from "node:assert/strict";
import test from "node:test";

import { performLogout } from "../src/logout.ts";

function steps(overrides = {}) {
  const chamadas = [];
  const base = {
    pushToken: async () => "ExponentPushToken[abc]",
    unregisterDevice: async () => { chamadas.push("unregister"); },
    disableLocalPush: async () => { chamadas.push("disableLocal"); },
    clearToken: async () => { chamadas.push("clearToken"); },
  };
  return { chamadas, deps: { ...base, ...overrides } };
}

test("caminho feliz: avisa o servidor e depois limpa a sessão", async () => {
  const { chamadas, deps } = steps();

  assert.deepEqual(await performLogout(deps), { serverOk: true });
  assert.deepEqual(chamadas, ["unregister", "disableLocal", "clearToken"]);
});

test("token expirado (401 no unregister) NÃO impede a saída", async () => {
  const { chamadas, deps } = steps({
    unregisterDevice: async () => { throw new Error("erro 401"); },
  });

  assert.deepEqual(await performLogout(deps), { serverOk: false });
  assert.ok(chamadas.includes("clearToken"), "a sessão local tem que sair de qualquer jeito");
});

test("falha ao buscar o push token também não trava a saída", async () => {
  const { chamadas, deps } = steps({
    pushToken: async () => { throw new Error("sem permissão"); },
  });

  assert.deepEqual(await performLogout(deps), { serverOk: false });
  assert.ok(chamadas.includes("clearToken"));
});

test("sem push token registrado, não chama o servidor e sai limpo", async () => {
  const { chamadas, deps } = steps({ pushToken: async () => null });

  assert.deepEqual(await performLogout(deps), { serverOk: true });
  assert.deepEqual(chamadas, ["disableLocal", "clearToken"]);
});

test("falha ao desligar o push local não trava a saída", async () => {
  const { chamadas, deps } = steps({
    disableLocalPush: async () => { throw new Error("boom"); },
  });

  assert.deepEqual(await performLogout(deps), { serverOk: false });
  assert.ok(chamadas.includes("clearToken"));
});

test("servidor aceita a conexão e não responde: o prazo vence e a saída segue", async () => {
  const { chamadas, deps } = steps({
    unregisterDevice: () => new Promise(() => {}),
    prazoMs: 20,
  });

  assert.deepEqual(await performLogout(deps), { serverOk: false });
  assert.deepEqual(chamadas, ["disableLocal", "clearToken"]);
});

test("o prazo ABORTA o request: o signal chega abortado ao unregister", async () => {
  let sinal;
  const { deps } = steps({
    unregisterDevice: (_t, signal) => {
      sinal = signal;
      return new Promise(() => {});
    },
    prazoMs: 20,
  });
  assert.deepEqual(await performLogout(deps), { serverOk: false });
  assert.equal(sinal.aborted, true);
});
