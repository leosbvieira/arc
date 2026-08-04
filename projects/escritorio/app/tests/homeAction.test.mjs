import assert from "node:assert/strict";
import test from "node:test";

import { actionForAt, nextAgendaAt } from "../src/homeAction.ts";

const empty = { staging: 0, anki: 0, reading: 0 };
const at = (value) => new Date(value);

test("prioriza os ritos pela hora e mantém revisão dominical acima do shutdown", () => {
  assert.equal(actionForAt(null, empty, at("2026-07-13T05:30:00-03:00")).target, "abertura");
  assert.equal(actionForAt(null, empty, at("2026-07-13T08:20:00-03:00")).target, "abertura");
  assert.equal(actionForAt(null, empty, at("2026-07-13T19:00:00-03:00")).target, "shutdown");
  assert.equal(actionForAt(null, empty, at("2026-07-12T20:00:00-03:00")).target, "revisao");
  assert.equal(actionForAt(null, empty, at("2026-07-13T21:00:00-03:00")).target, "fechar");
});

test("sessão pendente abre diretamente a leitura antes do rito noturno", () => {
  assert.equal(
    actionForAt(null, { ...empty, reading: 1 }, at("2026-07-13T18:00:00-03:00")).target,
    "leitura",
  );
});

test("agenda remove horários passados e ordena as próximas entradas", () => {
  const now = at("2026-07-13T15:00:00-03:00");
  const next = nextAgendaAt(
    [
      { hora: "09:00", ref: "passado" },
      { hora: "17:00", ref: "entrega" },
    ],
    [
      { hora: "16:00", titulo: "reunião", fonte: "gcal", inicio_ts: at("2026-07-13T16:00:00-03:00").getTime() / 1000 },
      { hora: "14:00", titulo: "encerrado", fonte: "outlook", inicio_ts: at("2026-07-13T14:00:00-03:00").getTime() / 1000 },
    ],
    "2026-07-13",
    now,
  );
  assert.deepEqual(next.map((item) => item.title), ["reunião", "entrega"]);
});
