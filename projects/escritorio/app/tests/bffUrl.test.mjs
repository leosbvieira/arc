import assert from "node:assert/strict";
import test from "node:test";

import { ambienteDoApp, bffUrlValidaOuNull, httpPermitido, validarBffUrl } from "../src/bffUrl.ts";

test("https válido: normaliza sem barra final", () => {
  assert.equal(validarBffUrl("  https://bff.exemplo.com/  ", false), "https://bff.exemplo.com");
  assert.equal(validarBffUrl("https://bff.exemplo.com:8443/api///", false), "https://bff.exemplo.com:8443/api");
});

test("http só passa quando permitido (desenvolvimento ou escape)", () => {
  assert.equal(validarBffUrl("http://192.168.0.2:8000", true), "http://192.168.0.2:8000");
  assert.throws(() => validarBffUrl("http://192.168.0.2:8000", false), /https/);
});

test("credenciais, query e hash são recusados", () => {
  assert.throws(() => validarBffUrl("https://leo:senha@bff.exemplo.com", false), /usuário\/senha/);
  assert.throws(() => validarBffUrl("https://bff.exemplo.com/?x=1", false), /\?/);
  assert.throws(() => validarBffUrl("https://bff.exemplo.com/#a", false), /#/);
});

test("lixo é recusado com mensagem em português", () => {
  assert.throws(() => validarBffUrl("", true), /informe/);
  assert.throws(() => validarBffUrl("192.168.0.2:8000", true), /inválido|https/);
  assert.throws(() => validarBffUrl("ftp://bff", true), /https/);
});

test("override salvo inválido vira null em vez de derrubar o boot", () => {
  assert.equal(bffUrlValidaOuNull("nada disso", true), null);
  assert.equal(bffUrlValidaOuNull(null, true), null);
  assert.equal(bffUrlValidaOuNull("https://ok.exemplo.com/", false), "https://ok.exemplo.com");
});

test("ambiente: sem variável é desenvolvimento; http permitido só lá ou com escape", () => {
  assert.equal(ambienteDoApp(undefined), "development");
  assert.equal(ambienteDoApp("preview"), "preview");
  assert.equal(ambienteDoApp("qualquer"), "development");
  assert.equal(httpPermitido("development", undefined), true);
  assert.equal(httpPermitido("preview", undefined), false);
  assert.equal(httpPermitido("preview", "1"), true);
  assert.equal(httpPermitido("production", undefined), false);
});
