import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_PARAMS, aplicar, decidir, fonteParaWiki, minutos, validar,
} from "../src/parametrosCore.ts";

const BOM = JSON.parse(JSON.stringify(DEFAULT_PARAMS));

function porta(inicial = null) {
  const estado = { valor: inicial, escritas: [], apagou: false };
  return {
    estado,
    ler: async () => estado.valor,
    gravar: async (v) => { estado.valor = v; estado.escritas.push(v); },
    apagar: async () => { estado.valor = null; estado.apagou = true; },
  };
}

const ok = (corpo) => ({ resposta: { ok: true, corpo }, cache: null });
const falha = (status, cache = null) => ({ resposta: { ok: false, status }, cache });
const envelope = (params, salvoEm = "2026-08-11T10:00:00.000Z") => ({ params, salvoEm });

// ---- validar ----
test("validar aceita um payload completo", () => {
  assert.deepEqual(validar(BOM), BOM);
});

test("validar recusa payload parcial, tipo errado, nulo e vazio", () => {
  const semTarifas = { ...BOM }; delete semTarifas.tarifas;
  assert.equal(validar(semTarifas), null);
  assert.equal(validar({ ...BOM, ritos: [{ slug: "x", hora: 530, dia: null }] }), null);
  assert.equal(validar(null), null);
  assert.equal(validar({ ...BOM, niveis: { limiares: [] } }), null);   // minItems
  assert.equal(validar({ ...BOM, ritos: [] }), null);                  // minItems
});

test("validar aceita dia nulo e recusa dia numérico", () => {
  assert.ok(validar({ ...BOM, ritos: [{ slug: "x", hora: "05:30", dia: null }] }));
  assert.equal(validar({ ...BOM, ritos: [{ slug: "x", hora: "05:30", dia: 3 }] }), null);
});

// ---- decidir ----
test("200 válido: fonte fresca e grava", () => {
  const d = decidir(ok(BOM));
  assert.equal(d.fonte.tipo, "fresco");
  assert.equal(d.cache, "gravar");
});

test("200 inválido não toca no cache bom", () => {
  const d = decidir({ resposta: { ok: true, corpo: { lixo: 1 } }, cache: envelope(BOM) });
  assert.equal(d.fonte.tipo, "cache");
  assert.equal(d.cache, "manter");
});

test("rede caiu com cache: usa cache com a data", () => {
  const d = decidir(falha(null, envelope(BOM)));
  assert.equal(d.fonte.tipo, "cache");
  assert.equal(d.fonte.salvoEm, "2026-08-11T10:00:00.000Z");
  assert.equal(d.cache, "manter");
});

test("rede caiu sem cache: cai no embutido, rotulado padrao", () => {
  const d = decidir(falha(null));
  assert.equal(d.fonte.tipo, "padrao");
  assert.deepEqual(d.fonte.params, DEFAULT_PARAMS);
  assert.equal(d.cache, "manter");
});

test("padrao nunca é confundido com fresco nem com cache", () => {
  assert.equal(decidir(ok(BOM)).fonte.tipo, "fresco");
  assert.equal(decidir(falha(null, envelope(BOM))).fonte.tipo, "cache");
  assert.equal(decidir(falha(null)).fonte.tipo, "padrao");
});

test("401 com cache continua legível; sem cache vira sessao", () => {
  assert.equal(decidir(falha(401, envelope(BOM))).fonte.tipo, "cache");
  assert.deepEqual(decidir(falha(401)).fonte, { tipo: "indisponivel", motivo: "sessao" });
});

test("cache sem salvoEm ou com salvoEm não-ISO é descartado", () => {
  for (const ruim of [{ params: BOM }, envelope(BOM, "ontem"), envelope(BOM, "")]) {
    const d = decidir({ resposta: { ok: false, status: null }, cache: ruim });
    assert.equal(d.fonte.tipo, "padrao");   // cache ruim não conta como cache
    assert.equal(d.cache, "descartar");
  }
});

test("precedência: resposta válida grava mesmo com cache corrompido", () => {
  const d = decidir({ resposta: { ok: true, corpo: BOM }, cache: { params: BOM } });
  assert.equal(d.fonte.tipo, "fresco");
  assert.equal(d.cache, "gravar");
});

// ---- aplicar ----
test("aplicar grava, mantém e apaga conforme o comando", async () => {
  const g = porta();
  await aplicar({ fonte: { tipo: "fresco", params: BOM }, cache: "gravar" }, g);
  assert.equal(g.estado.escritas.length, 1);
  assert.equal(g.estado.valor.params.tarifas.rotina, BOM.tarifas.rotina);
  assert.ok(g.estado.valor.salvoEm, "gravou sem salvoEm");

  const m = porta(envelope(BOM));
  await aplicar({ fonte: { tipo: "cache", params: BOM, salvoEm: "x" }, cache: "manter" }, m);
  assert.equal(m.estado.escritas.length, 0);
  assert.equal(m.estado.apagou, false);

  const a = porta(envelope(BOM));
  await aplicar({ fonte: { tipo: "indisponivel", motivo: "sessao" }, cache: "descartar" }, a);
  assert.equal(a.estado.apagou, true);
});

test("aplicar não propaga falha de escrita", async () => {
  const quebrada = { ler: async () => null, gravar: async () => { throw new Error("cheio"); }, apagar: async () => {} };
  await aplicar({ fonte: { tipo: "fresco", params: BOM }, cache: "gravar" }, quebrada);
});

test("duas decisões seguidas gravam em ordem", async () => {
  const p = porta();
  const a = { ...BOM, tarifas: { ...BOM.tarifas, rotina: 1 } };
  const b = { ...BOM, tarifas: { ...BOM.tarifas, rotina: 2 } };
  await aplicar({ fonte: { tipo: "fresco", params: a }, cache: "gravar" }, p);
  await aplicar({ fonte: { tipo: "fresco", params: b }, cache: "gravar" }, p);
  assert.deepEqual(p.estado.escritas.map((e) => e.params.tarifas.rotina), [1, 2]);
});

// ---- minutos e fonteParaWiki ----
test("minutos converte HH:MM", () => {
  assert.equal(minutos("00:00"), 0);
  assert.equal(minutos("18:30"), 1110);
  assert.equal(minutos("23:59"), 1439);
});

test("fonteParaWiki recusa o padrão e preserva o resto", () => {
  assert.deepEqual(fonteParaWiki({ tipo: "padrao", params: BOM }),
                   { tipo: "indisponivel", motivo: "sem-cache" });
  for (const f of [{ tipo: "fresco", params: BOM },
                   { tipo: "cache", params: BOM, salvoEm: "z" },
                   { tipo: "indisponivel", motivo: "sessao" }]) {
    assert.deepEqual(fonteParaWiki(f), f);
  }
});

test("DEFAULT_PARAMS é um Params válido", () => {
  assert.ok(validar(DEFAULT_PARAMS), "o embutido não passa no próprio schema");
});
