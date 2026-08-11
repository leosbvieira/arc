import assert from "node:assert/strict";
import test from "node:test";

import { montarEstante } from "../src/shelfView.ts";

const AGORA = 1_754_697_600_000; // ms
const DIA = 86_400_000;

function obra(over = {}) {
  return {
    id: 1,
    titulo: "Sapiens",
    status: "lendo",
    ciclo: 1,
    pagina_atual: 214,
    ultima_sessao: (AGORA - 3 * DIA) / 1000, // o servidor manda em segundos
    sessoes_n: 4,
    ...over,
  };
}

test("linha completa junta pagina e tempo", () => {
  const [linha] = montarEstante([obra()], AGORA);
  assert.equal(linha.titulo, "Sapiens");
  assert.equal(linha.detalhe, "pág. 214 · há 3 dias");
  assert.equal(linha.paginaInicialSugerida, "214");
});

test("obra sem sessao nao inventa pagina", () => {
  const [linha] = montarEstante(
    [obra({ pagina_atual: null, ultima_sessao: null, sessoes_n: 0 })],
    AGORA,
  );
  assert.equal(linha.detalhe, "ainda sem leitura");
  assert.equal(linha.paginaInicialSugerida, "");
});

test("obra lida sem pagina anotada mostra so o tempo", () => {
  const [linha] = montarEstante([obra({ pagina_atual: null })], AGORA);
  assert.equal(linha.detalhe, "há 3 dias");
  assert.equal(linha.paginaInicialSugerida, "");
});

test("tempo relativo cobre hoje, ontem, dias e semanas", () => {
  const casos = [
    [AGORA - 3600_000, "hoje"],
    [AGORA - 1.2 * DIA, "ontem"],
    [AGORA - 5 * DIA, "há 5 dias"],
    [AGORA - 7 * DIA, "há 1 semana"],
    [AGORA - 13 * DIA, "há 1 semana"],
    [AGORA - 14 * DIA, "há 2 semanas"],
    [AGORA - 70 * DIA, "há 10 semanas"],
  ];
  for (const [ms, esperado] of casos) {
    const [linha] = montarEstante([obra({ ultima_sessao: ms / 1000 })], AGORA);
    assert.ok(
      linha.detalhe.endsWith(esperado),
      `${linha.detalhe} deveria terminar com ${esperado}`,
    );
  }
});

test("leitura no futuro nao vira tempo negativo", () => {
  const [linha] = montarEstante([obra({ ultima_sessao: (AGORA + DIA) / 1000 })], AGORA);
  assert.ok(linha.detalhe.endsWith("hoje"));
});

// ---- recap (fatia 3) ----------------------------------------------------------

test("recap ausente vira null, venha ele como undefined, null ou vazio", () => {
  // Três fontes de "não tem": obra nova (campo ausente), servidor mandando null, e
  // sessão em que o modelo devolveu string vazia. A tela só quer saber de uma.
  const linhas = montarEstante(
    [
      { id: 1, titulo: "A", pagina_atual: null, ultima_sessao: null },
      { id: 2, titulo: "B", pagina_atual: null, ultima_sessao: null, recap: null },
      { id: 3, titulo: "C", pagina_atual: null, ultima_sessao: null, recap: "" },
    ],
    0,
  );
  assert.deepEqual(linhas.map((l) => l.recap), [null, null, null]);
});

test("recap presente atravessa intacto — a tela não reescreve o que o modelo disse", () => {
  const [linha] = montarEstante(
    [
      {
        id: 1,
        titulo: "Sapiens",
        pagina_atual: 42,
        ultima_sessao: 100,
        recap: "Você parou na tese da ordem imaginada.",
      },
    ],
    100_000,
  );
  assert.equal(linha.recap, "Você parou na tese da ordem imaginada.");
});
