import assert from "node:assert/strict";
import test from "node:test";

import { seedDecisions, buildClosingChecks } from "../src/closingChecks.ts";

const ROTINAS = [
  { slug: "acordar-5h30", feito: true },   // marcada de manhã
  { slug: "yoga", feito: true },           // marcada de manhã
  { slug: "diario", feito: false },
  { slug: "leitura", feito: false },
];

test("semeia como decidido só o que o servidor diz que já foi feito", () => {
  assert.deepEqual(seedDecisions(ROTINAS), {
    "acordar-5h30": true,
    yoga: true,
  });
});

test("rotina não tocada NÃO entra no payload — ausência não é furo", () => {
  const checks = buildClosingChecks(ROTINAS, seedDecisions(ROTINAS));
  const slugs = checks.map((c) => c.rotina);

  assert.ok(!slugs.includes("diario"));
  assert.ok(!slugs.includes("leitura"));
});

test("o que veio marcado de manhã sobrevive ao fechamento", () => {
  const checks = buildClosingChecks(ROTINAS, seedDecisions(ROTINAS));

  assert.deepEqual(
    checks.find((c) => c.rotina === "acordar-5h30"),
    { rotina: "acordar-5h30", feito: true },
  );
});

test("desmarcar explicitamente vira false — correção continua possível", () => {
  const decisoes = { ...seedDecisions(ROTINAS), yoga: false };
  const checks = buildClosingChecks(ROTINAS, decisoes);

  assert.deepEqual(
    checks.find((c) => c.rotina === "yoga"),
    { rotina: "yoga", feito: false },
  );
});

test("marcar à noite entra no payload", () => {
  const decisoes = { ...seedDecisions(ROTINAS), diario: true };
  const checks = buildClosingChecks(ROTINAS, decisoes);

  assert.deepEqual(
    checks.find((c) => c.rotina === "diario"),
    { rotina: "diario", feito: true },
  );
});

test("ignora decisão de rotina que não é do dia", () => {
  const checks = buildClosingChecks(ROTINAS, { "rotina-de-outro-dia": true });
  assert.deepEqual(checks, []);
});

test("sem nenhuma decisão o payload é vazio — fechar o dia nunca autoincrimina", () => {
  assert.deepEqual(buildClosingChecks(ROTINAS, {}), []);
});
