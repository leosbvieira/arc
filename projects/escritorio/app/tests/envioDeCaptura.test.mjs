// A ordem flush → GRAVA → POST → apaga, que antes não existia: o POST vinha antes da
// gravação, e matar o app no meio perdia texto e client_key.
import assert from "node:assert/strict";
import test from "node:test";

import { enviarCaptura } from "../src/envioDeCaptura.ts";
import { ehFalhaDeRede } from "../src/offlineError.ts";

const semRede = () => new TypeError("Network request failed");
const doServidor = (s) => new Error(`erro ${s}`);

function cenario({ flush = async () => ({ parou: null, rejeitados: 0 }), capture }) {
  const eventos = [];
  const fila = new Map();
  let n = 0;
  const deps = {
    flush: async () => {
      eventos.push("flush");
      return flush();
    },
    enqueue: async (item) => {
      const id = `q${++n}`;
      fila.set(id, item);
      eventos.push(`grava:${id}:${item.payload.client_key}`);
      return id;
    },
    removeQueued: async (id) => {
      eventos.push(`apaga:${id}`);
      return fila.delete(id);
    },
    capture: async (text, ck, sensivel) => {
      eventos.push(`post:${ck}`);
      return capture(text, ck, sensivel);
    },
    ehFalhaDeRede,
  };
  return { deps, eventos, fila };
}

const entrada = { text: "comprar pão", clientKey: "ck-1", sensivel: false, ts: 1 };

test("caminho feliz: grava ANTES do POST e apaga depois", async () => {
  const { deps, eventos, fila } = cenario({ capture: async () => "✅ anotado" });
  const r = await enviarCaptura(deps, entrada);
  assert.equal(r.tipo, "enviado");
  assert.equal(r.reply, "✅ anotado");
  assert.deepEqual(eventos, ["flush", "grava:q1:ck-1", "post:ck-1", "apaga:q1"]);
  assert.equal(fila.size, 0);
});

test("app morre durante o POST: o item já está na fila com a MESMA client_key", async () => {
  // Simula a morte como um POST que nunca resolve — observamos o estado da fila
  // no instante em que o POST foi disparado.
  const { deps, eventos, fila } = cenario({ capture: () => new Promise(() => {}) });
  void enviarCaptura(deps, entrada);
  await new Promise((r) => setTimeout(r, 0));
  assert.deepEqual(eventos, ["flush", "grava:q1:ck-1", "post:ck-1"]);
  assert.equal(fila.get("q1").payload.client_key, "ck-1");
});

test("falha de rede no POST: fica na fila, sem enfileirar de novo", async () => {
  const { deps, eventos, fila } = cenario({ capture: async () => { throw semRede(); } });
  const r = await enviarCaptura(deps, entrada);
  assert.deepEqual(r, { tipo: "guardado", motivo: "rede", rejeitados: 0 });
  assert.deepEqual(eventos, ["flush", "grava:q1:ck-1", "post:ck-1"]);
  assert.equal(fila.size, 1);
});

test("servidor recusou (404/500): sai da fila e o texto volta pra caixa", async () => {
  for (const status of [404, 500, 409]) {
    const { deps, eventos, fila } = cenario({ capture: async () => { throw doServidor(status); } });
    const r = await enviarCaptura(deps, entrada);
    assert.equal(r.tipo, "recusado");
    assert.equal(r.erro.message, `erro ${status}`);
    assert.deepEqual(eventos, ["flush", "grava:q1:ck-1", "post:ck-1", "apaga:q1"]);
    assert.equal(fila.size, 0);
  }
});

test("flush parou (rede/login): guarda direto, sem tentar o POST", async () => {
  for (const parou of ["rede", "login"]) {
    const { deps, eventos } = cenario({
      flush: async () => ({ parou, rejeitados: 0 }),
      capture: async () => { throw new Error("não devia chamar"); },
    });
    const r = await enviarCaptura(deps, entrada);
    assert.deepEqual(r, { tipo: "guardado", motivo: parou, rejeitados: 0 });
    assert.deepEqual(eventos, ["flush", "grava:q1:ck-1"]);
  }
});

test("rejeitados do flush são repassados pra tela atualizar o badge", async () => {
  const { deps } = cenario({
    flush: async () => ({ parou: null, rejeitados: 2 }),
    capture: async () => "ok",
  });
  const r = await enviarCaptura(deps, entrada);
  assert.equal(r.rejeitados, 2);
});
