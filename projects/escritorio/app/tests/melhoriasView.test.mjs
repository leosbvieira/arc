import assert from "node:assert/strict";
import test from "node:test";

import { agruparMelhorias } from "../src/melhoriasView.ts";

// A tela usa o tipo completo de api.ts; o agrupamento só exige estes campos.

function m(over) {
  return {
    id: 1,
    texto: "x",
    alvo: null,
    status: "novo",
    sensivel: 0,
    origem_captura_id: null,
    escolhida_semana: null,
    escolhida_em: null,
    criado: 1000,
    ...over,
  };
}

test("a escolhida da semana sai da fila e vira destaque", () => {
  const grupos = agruparMelhorias([
    m({ id: 1, alvo: "empresa", status: "escolhida", escolhida_semana: "2026-W32" }),
    m({ id: 2, alvo: "empresa" }),
  ]);

  assert.equal(grupos.escolhida?.id, 1);
  assert.deepEqual(grupos.porAlvo.empresa.map((i) => i.id), [2]);
});

test("sem alvo vai para a triagem, não para a fila", () => {
  const grupos = agruparMelhorias([m({ id: 1, alvo: null })]);

  assert.deepEqual(grupos.aTriar.map((i) => i.id), [1]);
  assert.deepEqual(grupos.porAlvo, { app: [], empresa: [], fluxo: [] });
});

test("feita e descartada não engrossam a fila", () => {
  // A fila só mostra o que ainda pede decisão; o resolvido vira histórico.
  const grupos = agruparMelhorias([
    m({ id: 1, alvo: "app", status: "feita" }),
    m({ id: 2, alvo: null, status: "descartada" }),
    m({ id: 3, alvo: "app" }),
  ]);

  assert.deepEqual(grupos.porAlvo.app.map((i) => i.id), [3]);
  assert.deepEqual(grupos.aTriar, []);
  assert.deepEqual(grupos.resolvidas.map((i) => i.id), [1, 2]);
});

test("mais recentes primeiro dentro de cada grupo", () => {
  const grupos = agruparMelhorias([
    m({ id: 1, alvo: "fluxo", criado: 100 }),
    m({ id: 2, alvo: "fluxo", criado: 300 }),
    m({ id: 3, alvo: "fluxo", criado: 200 }),
  ]);

  assert.deepEqual(grupos.porAlvo.fluxo.map((i) => i.id), [2, 3, 1]);
});

test("duas escolhidas: a mais recente vence e a outra volta pra fila", () => {
  // O servidor garante uma só, mas uma corrida entre dois aparelhos pode
  // entregar duas na mesma resposta. Mostrar duas "da semana" é o mesmo que
  // não ter escolhido nada — a tela precisa decidir sozinha.
  const grupos = agruparMelhorias([
    m({ id: 1, alvo: "app", status: "escolhida", escolhida_em: 100 }),
    m({ id: 2, alvo: "empresa", status: "escolhida", escolhida_em: 200 }),
  ]);

  assert.equal(grupos.escolhida?.id, 2);
  assert.deepEqual(grupos.porAlvo.app.map((i) => i.id), [1]);
});

test("alvo desconhecido não derruba a tela nem some do olho", () => {
  // Alvo novo vindo de um BFF mais novo que o APK: cai na triagem em vez de
  // sumir. Item invisível é item perdido, e a lei 1 vale para a fila também.
  const grupos = agruparMelhorias([m({ id: 1, alvo: "sistema" })]);

  assert.deepEqual(grupos.aTriar.map((i) => i.id), [1]);
});

test("lista vazia devolve todos os grupos, não undefined", () => {
  const grupos = agruparMelhorias([]);

  assert.equal(grupos.escolhida, null);
  assert.deepEqual(grupos.aTriar, []);
  assert.deepEqual(grupos.resolvidas, []);
  assert.deepEqual(grupos.vencidas, []);
  assert.deepEqual(grupos.porAlvo, { app: [], empresa: [], fluxo: [] });
});

// --- a semana da escolha vence -------------------------------------------------
//
// O BFF já filtra por semana no review; a TELA repetia a mentira por conta
// própria: uma escolha de junho aparecia sob o cabeçalho "desta semana". A semana
// corrente vem do servidor junto com a lista — nada de recalcular data no cliente,
// que é exatamente onde o projeto já se queimou com fuso.

test("escolha de outra semana não é a desta semana", () => {
  const grupos = agruparMelhorias(
    [m({ id: 1, alvo: "empresa", status: "escolhida", escolhida_semana: "2026-W26" })],
    "2026-W32",
  );

  assert.equal(grupos.escolhida, null);
  assert.deepEqual(grupos.vencidas.map((i) => i.id), [1]);
});

test("a escolha da semana corrente continua no topo", () => {
  const grupos = agruparMelhorias(
    [m({ id: 1, alvo: "empresa", status: "escolhida", escolhida_semana: "2026-W32" })],
    "2026-W32",
  );

  assert.equal(grupos.escolhida?.id, 1);
  assert.deepEqual(grupos.vencidas, []);
});

test("sem a semana do servidor a tela não inventa qual é a atual", () => {
  // APK novo falando com BFF antigo: sem `semana` na resposta não dá para decidir.
  // Classificar como vencida acusaria uma escolha legítima de estar velha — a tela
  // mantém o grupo e mostra a semana do próprio item no cabeçalho.
  const grupos = agruparMelhorias([
    m({ id: 1, alvo: "empresa", status: "escolhida", escolhida_semana: "2026-W32" }),
  ]);

  assert.equal(grupos.escolhida?.id, 1);
  assert.deepEqual(grupos.vencidas, []);
});

test("várias vencidas vêm da mais recente para a mais antiga", () => {
  const grupos = agruparMelhorias(
    [
      m({ id: 1, status: "escolhida", escolhida_semana: "2026-W26", escolhida_em: 100 }),
      m({ id: 2, status: "escolhida", escolhida_semana: "2026-W30", escolhida_em: 300 }),
    ],
    "2026-W32",
  );

  assert.deepEqual(grupos.vencidas.map((i) => i.id), [2, 1]);
});
