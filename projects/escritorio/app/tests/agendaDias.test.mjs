import assert from "node:assert/strict";
import test from "node:test";

import { faixaDeDias, rotuloDoDia } from "../src/agendaDias.ts";

// 23h30 no fuso do aparelho: em UTC já é o dia seguinte. Qualquer coisa derivada de
// toISOString() mostraria a semana errada exatamente no horário em que o Leo mais usa.
const NOITE = new Date(2026, 7, 4, 23, 30, 0);

test("a faixa começa HOJE no fuso do aparelho, não no UTC", () => {
  const dias = faixaDeDias(NOITE);
  assert.equal(dias[0].data, "2026-08-04");
});

test("mostra uma semana à frente", () => {
  const dias = faixaDeDias(NOITE);
  assert.equal(dias.length, 7);
  assert.equal(dias[6].data, "2026-08-10");
});

test("atravessa a virada do mês", () => {
  const dias = faixaDeDias(new Date(2026, 7, 30, 9, 0));
  assert.deepEqual(dias.map((d) => d.data).slice(0, 3), [
    "2026-08-30",
    "2026-08-31",
    "2026-09-01",
  ]);
});

test("os dois primeiros dias têm nome, o resto tem dia da semana", () => {
  const dias = faixaDeDias(NOITE);
  assert.equal(dias[0].rotulo, "hoje");
  assert.equal(dias[1].rotulo, "amanhã");
  assert.ok(dias[2].rotulo.length > 0 && dias[2].rotulo !== "amanhã");
});

test("o rótulo longo diz a data por extenso", () => {
  assert.match(rotuloDoDia("2026-08-04", NOITE), /hoje/i);
  assert.match(rotuloDoDia("2026-08-05", NOITE), /amanh/i);
  assert.match(rotuloDoDia("2026-08-11", NOITE), /11/);
});

test("data inválida não quebra a tela", () => {
  assert.equal(typeof rotuloDoDia("nao-e-data", NOITE), "string");
});
