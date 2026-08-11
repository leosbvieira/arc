import assert from "node:assert/strict";
import test from "node:test";

import {
  avisoDeObrasPresas,
  mensagemDeReconciliacao,
  mensagemDeTermino,
  mensagemDeTerminoFalho,
} from "../src/estanteResumo.ts";

test("terminar com sessões diz onde o resumão foi parar", () => {
  const msg = mensagemDeTermino({ titulo: "Sapiens", resumoTaskId: "t1" });
  assert.match(msg, /Sapiens saiu da estante/);
  assert.match(msg, /Staging/);
});

test("ciclo vazio não promete um resumão que não existe", () => {
  // É assim que ele tira da estante uma obra criada por engano.
  const msg = mensagemDeTermino({ titulo: "Criada sem querer", resumoTaskId: null });
  assert.match(msg, /Não havia sessão para resumir/);
  assert.doesNotMatch(msg, /Staging/);
});

test("falha do ClickUp diz que a obra NÃO voltou para a estante", () => {
  // A frase mais importante do módulo: se ele achar que nada aconteceu, termina de
  // novo e cria um segundo resumão para a mesma leitura.
  const msg = mensagemDeTerminoFalho("book_resumao_indisponivel");
  assert.match(msg, /ficou reservada/);
  assert.match(msg, /em vez de terminar de novo/);
});

test("obra já reservada não é tratada como erro do gesto dele", () => {
  assert.match(mensagemDeTerminoFalho("book_terminando"), /está fechando/);
  assert.match(mensagemDeTerminoFalho("book_terminando"), /resolver/);
});

test("sessão aberta e obra já terminada seguem com as frases da fatia 1", () => {
  assert.match(mensagemDeTerminoFalho("book_com_sessao_aberta"), /termine a sessão/);
  assert.match(mensagemDeTerminoFalho("book_ja_terminado"), /já tinha saído/);
});

test("detalhe desconhecido não vira silêncio nem eco de servidor", () => {
  assert.equal(mensagemDeTerminoFalho("coisa_nova_do_bff"), "não deu para terminar a obra");
  assert.equal(mensagemDeTerminoFalho(null), "não deu para terminar a obra");
});

test("reconciliar diz qual dos dois mundos era o verdadeiro", () => {
  assert.match(
    mensagemDeReconciliacao("terminado", "Sapiens"),
    /já existia no Staging/,
  );
  assert.match(
    mensagemDeReconciliacao("liberado", "Sapiens"),
    /Nenhum resumão foi criado.*voltou para a estante/,
  );
});

test("sem obra presa não há aviso — silêncio é o estado normal", () => {
  assert.equal(avisoDeObrasPresas(0), null);
  assert.equal(avisoDeObrasPresas(-1), null);
});

test("singular e plural do aviso de obra presa", () => {
  assert.equal(avisoDeObrasPresas(1), "1 obra ficou fechando sem resposta do ClickUp");
  assert.match(avisoDeObrasPresas(3), /^3 obras ficaram/);
});
