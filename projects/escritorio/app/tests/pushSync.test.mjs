import assert from "node:assert/strict";
import test from "node:test";

import { sincronizarPush } from "../src/pushSync.ts";

function cenario({ registrado = null, atual, unregister } = {}) {
  const chamadas = [];
  let lembrado = registrado;
  const deps = {
    registrado: async () => registrado,
    atual: async () => atual,
    registerDevice: async (t) => {
      chamadas.push(`register:${t}`);
    },
    unregisterDevice: async (t) => {
      chamadas.push(`unregister:${t}`);
      if (unregister) await unregister(t);
    },
    lembrar: async (t) => {
      chamadas.push(`lembrar:${t}`);
      lembrado = t;
    },
    esquecer: async () => {
      chamadas.push("esquecer");
      lembrado = null;
    },
  };
  return { deps, chamadas, lembrado: () => lembrado };
}

const ok = (token) => ({ token, motivo: "ok" });

test("primeiro boot: registra e lembra", async () => {
  const { deps, chamadas, lembrado } = cenario({ atual: ok("T1") });
  assert.deepEqual(await sincronizarPush(deps), { tipo: "registrado", token: "T1" });
  assert.deepEqual(chamadas, ["register:T1", "lembrar:T1"]);
  assert.equal(lembrado(), "T1");
});

test("mesmo token: re-registra (idempotente) e não remove nada", async () => {
  const { deps, chamadas } = cenario({ registrado: "T1", atual: ok("T1") });
  assert.deepEqual(await sincronizarPush(deps), { tipo: "registrado", token: "T1" });
  assert.deepEqual(chamadas, ["register:T1", "lembrar:T1"]);
});

test("rotação: registra o novo ANTES de tirar o velho", async () => {
  const { deps, chamadas, lembrado } = cenario({ registrado: "T1", atual: ok("T2") });
  const r = await sincronizarPush(deps);
  assert.deepEqual(r, { tipo: "rotacionado", token: "T2", anterior: "T1", anteriorRemovido: true });
  assert.deepEqual(chamadas, ["register:T2", "lembrar:T2", "unregister:T1"]);
  assert.equal(lembrado(), "T2");
});

test("rotação com falha ao remover o velho: o novo fica valendo mesmo assim", async () => {
  const { deps, lembrado } = cenario({
    registrado: "T1",
    atual: ok("T2"),
    unregister: async () => {
      throw new Error("erro 500");
    },
  });
  const r = await sincronizarPush(deps);
  assert.equal(r.tipo, "rotacionado");
  assert.equal(r.anteriorRemovido, false);
  assert.equal(lembrado(), "T2");
});

test("permissão revogada com token registrado: tira do servidor e esquece", async () => {
  const { deps, chamadas, lembrado } = cenario({
    registrado: "T1",
    atual: { token: null, motivo: "permissao_negada" },
  });
  const r = await sincronizarPush(deps);
  assert.deepEqual(r, { tipo: "revogado", anterior: "T1", removidoNoServidor: true });
  assert.deepEqual(chamadas, ["unregister:T1", "esquecer"]);
  assert.equal(lembrado(), null);
});

test("permissão revogada, servidor fora: NÃO esquece — a próxima abertura tenta de novo", async () => {
  const { deps, chamadas, lembrado } = cenario({
    registrado: "T1",
    atual: { token: null, motivo: "permissao_negada" },
    unregister: async () => {
      throw new TypeError("Network request failed");
    },
  });
  const r = await sincronizarPush(deps);
  assert.deepEqual(r, { tipo: "revogado", anterior: "T1", removidoNoServidor: false });
  assert.deepEqual(chamadas, ["unregister:T1"]);
  assert.equal(lembrado(), "T1");
});

test("emulador / Expo Go com token antigo guardado: não mexe no servidor", async () => {
  for (const motivo of ["emulador", "sem_projectId"]) {
    const { deps, chamadas } = cenario({ registrado: "T1", atual: { token: null, motivo } });
    assert.deepEqual(await sincronizarPush(deps), { tipo: "sem_push", motivo });
    assert.deepEqual(chamadas, []);
  }
});

test("sem token e sem nada registrado: nada a fazer", async () => {
  const { deps, chamadas } = cenario({ atual: { token: null, motivo: "permissao_negada" } });
  assert.deepEqual(await sincronizarPush(deps), { tipo: "sem_push", motivo: "permissao_negada" });
  assert.deepEqual(chamadas, []);
});

test("registerDevice falhou: propaga e NÃO lembra o token (a próxima abertura repete)", async () => {
  const { deps, lembrado } = cenario({ registrado: "T1", atual: ok("T2") });
  deps.registerDevice = async () => {
    throw new Error("erro 503");
  };
  await assert.rejects(sincronizarPush(deps), /503/);
  assert.equal(lembrado(), "T1");
});
