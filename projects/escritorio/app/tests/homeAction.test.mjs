import assert from "node:assert/strict";
import test from "node:test";

import { minutos } from "../src/parametrosCore.ts";
import { actionForAt, nextAgendaAt } from "../src/homeAction.ts";

const empty = { staging: 0, anki: 0, reading: 0 };
const at = (value) => new Date(value);

const RITOS = [
  { slug: "toque", hora: "05:30", dia: null },
  { slug: "checkin", hora: "08:20", dia: null },
  { slug: "jornal", hora: "08:30", dia: null },
  { slug: "digest", hora: "09:00", dia: null },
  { slug: "shutdown", hora: "19:00", dia: null },
  { slug: "closing", hora: "21:00", dia: null },
  { slug: "review", hora: "20:00", dia: "domingo" },
];
const com = (over) => RITOS.map((r) => ({ ...r, ...(over[r.slug] ?? {}) }));

test("prioriza os ritos pela hora e mantém revisão dominical acima do shutdown", () => {
  assert.equal(actionForAt(null, empty, RITOS, at("2026-07-13T05:30:00-03:00")).target, "abertura");
  assert.equal(actionForAt(null, empty, RITOS, at("2026-07-13T08:20:00-03:00")).target, "abertura");
  assert.equal(actionForAt(null, empty, RITOS, at("2026-07-13T19:00:00-03:00")).target, "shutdown");
  assert.equal(actionForAt(null, empty, RITOS, at("2026-07-12T20:00:00-03:00")).target, "revisao");
  assert.equal(actionForAt(null, empty, RITOS, at("2026-07-13T21:00:00-03:00")).target, "fechar");
});

test("sessão pendente abre diretamente a leitura antes do rito noturno", () => {
  assert.equal(
    actionForAt(null, { ...empty, reading: 1 }, RITOS, at("2026-07-13T18:00:00-03:00")).target,
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

// --- Modo Retorno (lei 4: dia quebrado = replanejar, nunca pilha de culpa) ---

test("ausência de 7+ dias vira 'voltar hoje', não a pilha de atrasadas", () => {
  const acao = actionForAt(null, { dias_ausente: 10 }, RITOS, new Date(2026, 7, 4, 21, 30));

  assert.equal(acao.target, "capturar");
  assert.match(acao.eyebrow + acao.title, /volt/i);
});

test("Modo Retorno vence QUALQUER rito do horário", () => {
  // 21h30 normalmente manda fechar o dia; voltando de 10 dias, não.
  const rito = actionForAt(null, {}, RITOS, new Date(2026, 7, 4, 21, 30));
  const retorno = actionForAt(null, { dias_ausente: 10 }, RITOS, new Date(2026, 7, 4, 21, 30));

  assert.equal(rito.target, "fechar");
  assert.notEqual(retorno.target, "fechar");
});

test("6 dias ainda não é retorno — o limiar é 7", () => {
  assert.equal(
    actionForAt(null, { dias_ausente: 6 }, RITOS, new Date(2026, 7, 4, 21, 30)).target,
    "fechar",
  );
});

test("sem informação de ausência nada muda", () => {
  assert.equal(
    actionForAt(null, {}, RITOS, new Date(2026, 7, 4, 21, 30)).target,
    "fechar",
  );
});

// --- Os limiares seguem a tabela de ritos, não hora cravada no código ---

test("os limiares de rito seguem a tabela: shutdown movido move o hero", () => {
  const ritos = com({ shutdown: { hora: "18:00" } });
  const as18 = at("2026-07-13T18:05:00-03:00");
  assert.equal(actionForAt(null, empty, RITOS, as18).target, "tarefas");
  assert.equal(actionForAt(null, empty, ritos, as18).target, "shutdown");
});

test("rito com minuto não-zero: antes, no instante e depois", () => {
  const ritos = com({ shutdown: { hora: "18:30" } });
  const alvo = (hhmm) => actionForAt(null, empty, ritos, at(`2026-07-13T${hhmm}:00-03:00`)).target;
  assert.equal(alvo("18:29"), "tarefas");
  assert.equal(alvo("18:30"), "shutdown");
  assert.equal(alvo("18:31"), "shutdown");
});

test("o domingo deriva review menos 3h", () => {
  const cedo = com({ review: { hora: "18:00" } });   // limiar vira 15:00
  const as16 = at("2026-07-12T16:00:00-03:00");      // domingo
  assert.notEqual(actionForAt(null, empty, RITOS, as16).target, "revisao");
  assert.equal(actionForAt(null, empty, cedo, as16).target, "revisao");
});

test("os dois prazos NÃO derivam de rito nenhum", () => {
  const tarde = com({ toque: { hora: "09:00" }, checkin: { hora: "11:00" } });
  const as7 = at("2026-07-13T07:00:00-03:00");
  assert.equal(actionForAt(null, empty, RITOS, as7).target, "abertura");
  assert.equal(actionForAt(null, empty, tarde, as7).target, "abertura");
});

test("minutos e a tabela concordam", () => {
  assert.equal(minutos("18:30"), 1110);
});
