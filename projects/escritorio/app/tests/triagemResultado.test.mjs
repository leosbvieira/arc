import assert from "node:assert/strict";
import test from "node:test";

import { resumoDaTriagem } from "../src/triagemResultado.ts";

const ok = (id) => ({ task_id: id, ok: true, erro: null });
const falha = (id, erro) => ({ task_id: id, ok: false, erro });

test("lote inteiro certo não menciona falha nenhuma", () => {
  const msg = resumoDaTriagem([ok("a"), ok("b")]);
  assert.equal(msg, "2 tarefas movidas.");
  assert.doesNotMatch(msg, /não movida/);
});

test("uma só usa o singular — '1 tarefas movidas' é o tipo de coisa que ele nota", () => {
  assert.equal(resumoDaTriagem([ok("a")]), "1 tarefa movida.");
});

test("o caso que motivou o módulo: 0 movidas, 1 não movida, e AGORA diz por quê", () => {
  const msg = resumoDaTriagem([falha("a", "HTTPStatusError")]);
  assert.match(msg, /0 movidas · 1 não movida\./);
  // Antes esta linha inteira era descartada pela tela.
  assert.match(msg, /Tasks in Multiple Lists/);
});

test("proposta velha sobre tarefa que já saiu da fila é dita em português", () => {
  assert.match(resumoDaTriagem([falha("a", "fora_do_staging")]), /já tinha saído do Staging/);
});

test("classe de exceção desconhecida aparece crua em vez de sumir", () => {
  // Se o BFF passar a estourar outra coisa, a tela não pode emudecer.
  assert.match(resumoDaTriagem([falha("a", "SSLError")]), /falha inesperada \(SSLError\)/);
});

test("falha sem causa ainda produz uma linha", () => {
  // `ok: false` com `erro: null` não deveria existir; se existir, não pode virar silêncio.
  const msg = resumoDaTriagem([falha("a", null)]);
  assert.match(msg, /1 não movida/);
  assert.match(msg, /sem causa informada/);
});

test("causas diferentes viram linhas diferentes, com a contagem de cada uma", () => {
  const msg = resumoDaTriagem([
    ok("a"),
    falha("b", "HTTPStatusError"),
    falha("c", "HTTPStatusError"),
    falha("d", "fora_do_staging"),
  ]);
  assert.match(msg, /1 movida · 3 não movidas\./);
  assert.match(msg, /2: o ClickUp recusou o movimento/);
  assert.match(msg, /1: já tinha saído do Staging/);
});

test("causa única não recebe contagem redundante", () => {
  // "2: não deu para falar" quando são exatamente as 2 falhas do lote é ruído.
  const msg = resumoDaTriagem([falha("a", "ReadTimeout"), falha("b", "ReadTimeout")]);
  assert.match(msg, /0 movidas · 2 não movidas\.\n\nnão deu para falar com o ClickUp/);
});

test("mensagem remota NÃO é ecoada — o título da tarefa não vai para a tela", () => {
  // O BFF manda só o nome da classe de propósito (lei 7). Se um dia passar a mandar a
  // mensagem inteira, ela vem com o título da tarefa dentro; o ramo default só ecoa o
  // que parece código.
  const msg = resumoDaTriagem([falha("a", "Task 'Comprar Minancora' not found in list")]);
  assert.equal(msg, "0 movidas · 1 não movida.\n\nfalha inesperada");
  assert.doesNotMatch(msg, /Minancora/);
});
