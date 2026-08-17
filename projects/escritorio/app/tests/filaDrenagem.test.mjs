// O laço que o `catch { break }` habitava. Ele nunca teve teste porque morava dentro
// de captureQueue.ts, que importa expo-secure-store — e foi exatamente por isso que o
// bug de head-of-line blocking sobreviveu a vida inteira do arquivo.
import assert from "node:assert/strict";
import test from "node:test";

import { drenar } from "../src/filaDrenagem.ts";
import { decidirAposFalha, paraAFila } from "../src/offlineError.ts";

const semRede = () => new TypeError("Network request failed");
const doServidor = (s) => new Error(`erro ${s}`);

/** Fila de mentira que registra tudo que aconteceu, na ordem. */
function filaFalsa(itens, enviar) {
  let idx = itens.map((it) => ({ id: it.id, chunks: 1, tentativas: it.tentativas }));
  const eventos = [];
  const conteudo = new Map(itens.map((it) => [it.id, it]));
  const escaninho = [];
  return {
    eventos,
    escaninho,
    get idx() {
      return idx;
    },
    deps: {
      lerIndice: async () => idx,
      gravarIndice: async (novo) => {
        idx = novo;
        eventos.push(`grava:[${novo.map((e) => e.id).join(",")}]`);
      },
      lerItem: async (e) => {
        const it = conteudo.get(e.id);
        if (!it) throw new Error("envenenado");
        return it;
      },
      apagarItem: async (e) => eventos.push(`apaga:${e.id}`),
      enviar: async (item) => {
        eventos.push(`envia:${item.id}`);
        await enviar(item);
      },
      arquivarRejeitado: async (e) => {
        escaninho.push(e);
        eventos.push(`arquiva:${e.id}`);
      },
      decidir: decidirAposFalha,
      paraAFila,
    },
  };
}

test("fila boa drena inteira", async () => {
  const f = filaFalsa([{ id: "a" }, { id: "b" }], async () => {});
  const r = await drenar(f.deps);
  assert.deepEqual(r, { restantes: 0, parou: null, rejeitados: 0 });
  assert.equal(f.idx.length, 0);
});

test("O BUG: um 404 eterno na cabeça não segura mais quem está atrás", async () => {
  // Antes, `catch { break }` parava aqui e "b" nunca era enviado — nem hoje, nem
  // nunca, porque toda drenagem futura reencontrava "a" na cabeça.
  const f = filaFalsa([{ id: "a" }, { id: "b" }], async (item) => {
    if (item.id === "a") throw doServidor(404);
  });
  const r = await drenar(f.deps);
  assert.ok(f.eventos.includes("envia:b"), "o item de trás foi entregue");
  assert.equal(r.restantes, 1, "só o recusado ficou");
  assert.equal(f.idx[0].id, "a");
  assert.equal(f.idx[0].tentativas, 1);
});

test("sem rede para tudo e NÃO gasta tentativa", async () => {
  const f = filaFalsa([{ id: "a" }, { id: "b" }], async () => {
    throw semRede();
  });
  const r = await drenar(f.deps);
  assert.equal(r.parou, "rede");
  assert.equal(r.restantes, 2, "ninguém sai da fila");
  assert.equal(f.idx[0].tentativas, undefined, "tentativa intocada");
  assert.ok(!f.eventos.includes("envia:b"), "nem tenta o resto");
});

test("401 para a fila e se distingue de queda de rede", async () => {
  const f = filaFalsa([{ id: "a" }], async () => {
    throw doServidor(401);
  });
  const r = await drenar(f.deps);
  assert.equal(r.parou, "login", "a tela precisa dizer 'entre de novo', não 'sem conexão'");
  assert.equal(f.idx[0].tentativas, undefined);
});

test("a drenagem não gira para sempre quando só sobram recusados", async () => {
  // A rotação cria o risco de laço infinito; `jaFalharamAgora` é o que o fecha.
  const f = filaFalsa([{ id: "a" }, { id: "b" }], async () => {
    throw doServidor(404);
  });
  const r = await drenar(f.deps);
  assert.equal(r.restantes, 2);
  assert.equal(f.eventos.filter((e) => e === "envia:a").length, 1, "cada um tentado uma vez");
  assert.equal(f.eventos.filter((e) => e === "envia:b").length, 1);
});

test("na última tentativa o item vai pro escaninho ANTES de sair do índice", async () => {
  // A ordem é o conserto: de-indexar primeiro deixava o item fora dos DOIS índices se
  // o processo morresse (ou se o arquivamento lançasse) entre as duas escritas.
  const f = filaFalsa([{ id: "a", tentativas: 4 }], async () => {
    throw doServidor(500);
  });
  const r = await drenar(f.deps);
  assert.equal(r.rejeitados, 1);
  assert.deepEqual(f.escaninho.map((e) => e.id), ["a"]);
  const iArquiva = f.eventos.indexOf("arquiva:a");
  const iGrava = f.eventos.findIndex((e, i) => i > iArquiva - 2 && e.startsWith("grava:"));
  assert.ok(iArquiva < iGrava, `arquiva antes de gravar o índice: ${f.eventos.join(" ")}`);
  assert.equal(f.idx.length, 0);
});

test("um throw do arquivamento não some com o item", async () => {
  const f = filaFalsa([{ id: "a", tentativas: 4 }], async () => {
    throw doServidor(500);
  });
  f.deps.arquivarRejeitado = async () => {
    throw new Error("SecureStore cheio");
  };
  await assert.rejects(() => drenar(f.deps));
  // O índice ainda tem o item: ele não foi removido antes de ser preservado.
  assert.equal(f.idx.length, 1, "a fila ainda o conhece");
});

test("item envenenado é descartado sem travar a fila", async () => {
  const f = filaFalsa([{ id: "a" }, { id: "b" }], async () => {});
  f.deps.lerItem = async (e) => {
    if (e.id === "a") throw new Error("json corrompido");
    return { id: e.id };
  };
  const r = await drenar(f.deps);
  assert.equal(r.restantes, 0);
  assert.ok(f.eventos.includes("envia:b"));
  // De-indexa ANTES de apagar os chunks: órfão inofensivo > fantasma preso.
  assert.ok(f.eventos.indexOf("grava:[b]") < f.eventos.indexOf("apaga:a"));
});

test("o recusado não bloqueia, mas também não é entregue duas vezes", async () => {
  const enviados = [];
  const f = filaFalsa([{ id: "a" }, { id: "b" }, { id: "c" }], async (item) => {
    enviados.push(item.id);
    if (item.id === "b") throw doServidor(404);
  });
  await drenar(f.deps);
  assert.deepEqual(enviados, ["a", "b", "c"]);
  assert.equal(f.idx.length, 1);
  assert.equal(f.idx[0].id, "b");
});
