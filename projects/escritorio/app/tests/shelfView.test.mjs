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
