import assert from "node:assert/strict";
import test from "node:test";

import { parseReadingEntry } from "../src/readingParser.ts";

test("extrai os comandos de leitura sem alterar o conteúdo", () => {
  const cases = [
    ["citação: texto", "citação", "texto"],
    ["citacao texto", "citação", "texto"],
    ["CITAÇÃO, texto", "citação", "texto"],
    ["citação texto", "citação", "texto"],
    ["quote: text", "citação", "text"],
    ["quote text", "citação", "text"],
    ["citação “Ser ou não ser”", "citação", "“Ser ou não ser”"],
    ["citação texto: complemento", "citação", "texto: complemento"],
    ["comentário: reflexão", "comentário", "reflexão"],
    ["ideia plano", "ideia", "plano"],
    ["lista, item", "lista", "item"],
  ];

  for (const [input, kind, text] of cases) {
    assert.deepEqual(parseReadingEntry(input), { kind, text });
  }
});

test("não trata prefixos parecidos ou menções no meio como comando", () => {
  for (const input of ["citar o autor", "citacaozinha", "uma citação no meio"]) {
    assert.deepEqual(parseReadingEntry(input), {
      kind: "comentário",
      text: input,
    });
  }
});

test("comando vazio não produz conteúdo e livro usa o mesmo protocolo", () => {
  assert.deepEqual(parseReadingEntry("citação"), {
    kind: "citação",
    text: "",
  });
  assert.deepEqual(parseReadingEntry("livro: Dom Casmurro"), {
    book: "Dom Casmurro",
    text: "",
  });
});
