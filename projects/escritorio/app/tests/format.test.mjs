import assert from "node:assert/strict";
import test from "node:test";

import { milhar } from "../src/format.ts";

// Separador de milhar em pt-BR sem depender de Intl: o Hermes não garante Intl e,
// onde ele falta, toLocaleString não quebra — devolve "1553" sem separador, calado.
// O valor absoluto é CONTRATO, não descuido: quem chama escreve o sinal
// (`−{milhar(semana.desconto)}`), e `desconto` já chega positivo do BFF.

test("milhar: sem separador abaixo de 1000", () => {
  assert.equal(milhar(0), "0");
  assert.equal(milhar(999), "999");
});

test("milhar: separador de milhar e de milhão", () => {
  assert.equal(milhar(1000), "1.000");
  assert.equal(milhar(1553), "1.553");
  assert.equal(milhar(1000000), "1.000.000");
});

test("milhar: negativo vira absoluto — quem chama põe o sinal", () => {
  assert.equal(milhar(-40), "40");
});
