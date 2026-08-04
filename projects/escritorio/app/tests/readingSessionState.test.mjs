import assert from "node:assert/strict";
import test from "node:test";

import {
  canClearLocalAfterDiscardFailure,
  formatReadingElapsed,
  normalizeReadingActiveSeconds,
} from "../src/readingSessionState.ts";

test("cronometro diferencia minutos de horas", () => {
  assert.equal(formatReadingElapsed(0), "0m 00s");
  assert.equal(formatReadingElapsed(59), "0m 59s");
  assert.equal(formatReadingElapsed(60), "1m 00s");
  assert.equal(formatReadingElapsed(3599), "59m 59s");
  assert.equal(formatReadingElapsed(3600), "1h 00m");
  assert.equal(formatReadingElapsed(264_420), "73h 27m");
});

test("descarte local so aceita estados remotos terminais", () => {
  assert.equal(canClearLocalAfterDiscardFailure("reading_session_compiled"), true);
  assert.equal(canClearLocalAfterDiscardFailure("reading_session_discarded"), true);
  assert.equal(canClearLocalAfterDiscardFailure("reading_session_nao_encontrada"), true);
  assert.equal(canClearLocalAfterDiscardFailure("reading_session_compiling"), false);
  assert.equal(canClearLocalAfterDiscardFailure("reading_timeout"), false);
  assert.equal(canClearLocalAfterDiscardFailure(null), false);
});

test("duracao ativa migra rascunho antigo sem contar dias fechado", () => {
  assert.equal(normalizeReadingActiveSeconds(125.9, 1_000, 99_000), 125);
  assert.equal(normalizeReadingActiveSeconds(undefined, 1_000, 61_000), 60);
  assert.equal(normalizeReadingActiveSeconds(undefined, 61_000, 1_000), 0);
  assert.equal(normalizeReadingActiveSeconds(undefined, 0, 999_999_999), 86_400);
});
