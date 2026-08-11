import assert from "node:assert/strict";
import test from "node:test";

import { DEFAULT_PARAMS } from "../src/parametrosCore.ts";
import { closingReward, closingLabel } from "../src/closingPoints.ts";

const POINTS = DEFAULT_PARAMS.tarifas;

// A régua é o mockup aprovado (proposta-c2-sobria.html, rito "Fechar o dia") e os
// cinco casos de aceite decididos pelo Leo (ONDA1-CORRECOES.md). A assinatura é
// (marcadas, totalRotinas, temTexto, points):
//
// - garantido = o que o toque registra AGORA, em função do dia inteiro:
//   fechamento + (marcadas × rotina) + (temTexto ? despejo : 0).
// - teto = o máximo DO DIA, constante enquanto ele trabalha:
//   fechamento + (total × rotina) + despejo.
// O garantido SOBE conforme ele marca, o teto NÃO se move, e quando ele marca
// tudo e escreve, garantido === teto — o rótulo colapsa para "garante +N".
// A tabela é a real de DEFAULT_PARAMS.tarifas — se os valores mudarem lá, este
// teste avisa.

test("aceite 1 (mockup): 1 rotina no dia, 0 marcadas, sem texto → garante +80 · bônus até +140", () => {
  assert.deepEqual(closingReward(0, 1, false, POINTS), { garantido: 80, teto: 140 });
  assert.equal(closingLabel(0, 1, false, POINTS), "garante +80 · bônus até +140");
});

test("aceite 2: 1 rotina no dia, 1 marcada, com texto → garante +140", () => {
  assert.deepEqual(closingReward(1, 1, true, POINTS), { garantido: 140, teto: 140 });
  assert.equal(closingLabel(1, 1, true, POINTS), "garante +140");
});

test("aceite 3: 5 rotinas, 4 marcadas de manhã, sem texto → garante +160 · bônus até +220", () => {
  assert.deepEqual(closingReward(4, 5, false, POINTS), { garantido: 160, teto: 220 });
  assert.equal(closingLabel(4, 5, false, POINTS), "garante +160 · bônus até +220");
});

test("aceite 4: 5 rotinas, 5 marcadas, com texto → garante +220", () => {
  assert.deepEqual(closingReward(5, 5, true, POINTS), { garantido: 220, teto: 220 });
  assert.equal(closingLabel(5, 5, true, POINTS), "garante +220");
});

test("aceite 5: 0 rotinas no dia, sem texto → garante +80 · bônus até +120", () => {
  assert.deepEqual(closingReward(0, 0, false, POINTS), { garantido: 80, teto: 120 });
  assert.equal(closingLabel(0, 0, false, POINTS), "garante +80 · bônus até +120");
});

test("garantido absorve as rotinas já marcadas e o despejo quando já há texto", () => {
  // o número SOBE conforme ele marca — a promessa não encolhe quando ele obedece
  assert.equal(closingReward(0, 3, false, POINTS).garantido, 80);
  assert.equal(closingReward(1, 3, false, POINTS).garantido, 100);
  assert.equal(closingReward(2, 3, true, POINTS).garantido, 160);
});

test("teto é o máximo do dia: constante enquanto ele trabalha", () => {
  const teto = 80 + 3 * 20 + 40;
  assert.equal(closingReward(0, 3, false, POINTS).teto, teto);
  assert.equal(closingReward(2, 3, false, POINTS).teto, teto);
  // nem o texto derruba o teto — é o mesmo dia, o mesmo máximo
  assert.equal(closingReward(2, 3, true, POINTS).teto, teto);
});

test("tudo marcado e com texto: nada mais a ganhar — rótulo sem a parte de bônus", () => {
  assert.deepEqual(closingReward(3, 3, true, POINTS), { garantido: 180, teto: 180 });
  assert.equal(closingLabel(3, 3, true, POINTS), "garante +180");
});

test("zero rotinas no dia é legítimo: fecha pelos +80, bônus só do despejo", () => {
  assert.equal(closingLabel(0, 0, false, POINTS), "garante +80 · bônus até +120");
  assert.equal(closingLabel(0, 0, true, POINTS), "garante +120");
});

test("o que falta para o teto é o que ele ainda pode fazer hoje", () => {
  // com texto e 2 de 4 rotinas marcadas, restam 2 rotinas ainda não creditadas
  assert.equal(closingLabel(2, 4, true, POINTS), "garante +160 · bônus até +200");
});
