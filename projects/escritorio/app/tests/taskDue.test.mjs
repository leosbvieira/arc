import assert from "node:assert/strict";
import test from "node:test";

import { dueFromChoice, horaValida } from "../src/taskDue.ts";

// 04/ago/2026 às 23h30 no fuso do aparelho. É a hora perigosa: em UTC já é dia 05,
// então qualquer coisa derivada de toISOString() erraria o dia inteiro.
const NOITE = new Date(2026, 7, 4, 23, 30, 0);

test("sem prazo devolve null — continua possível criar tarefa solta", () => {
  assert.equal(dueFromChoice(null, NOITE), null);
});

test("hoje usa o dia do APARELHO, não o UTC", () => {
  assert.equal(dueFromChoice("hoje", NOITE), "2026-08-04");
});

test("amanhã soma um dia", () => {
  assert.equal(dueFromChoice("amanha", NOITE), "2026-08-05");
});

test("em 7 dias soma uma semana", () => {
  assert.equal(dueFromChoice("semana", NOITE), "2026-08-11");
});

test("atravessa a virada do mês", () => {
  assert.equal(dueFromChoice("amanha", new Date(2026, 7, 31, 9, 0, 0)), "2026-09-01");
});

test("atravessa a virada do ano", () => {
  assert.equal(dueFromChoice("amanha", new Date(2026, 11, 31, 9, 0, 0)), "2027-01-01");
});

test("zero-padding de mês e dia", () => {
  assert.equal(dueFromChoice("hoje", new Date(2026, 0, 5, 9, 0, 0)), "2026-01-05");
});

test("hora só é aceita no formato civil que o BFF valida", () => {
  for (const boa of ["00:00", "09:05", "15:30", "23:59"]) {
    assert.equal(horaValida(boa), true, boa);
  }
  for (const ruim of ["24:00", "9:05", "15:60", "1530", "15h30", "", "abc"]) {
    assert.equal(horaValida(ruim), false, ruim);
  }
});
