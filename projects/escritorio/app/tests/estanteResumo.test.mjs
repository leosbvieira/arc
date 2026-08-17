import assert from "node:assert/strict";
import test from "node:test";

import {
  avisoDeObrasPresas,
  mensagemDeReconciliacao,
  mensagemDeResolucaoFalha,
  mensagemDeTermino,
  mensagemDeTerminoFalho,
  resolucaoMudouEstado,
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

test("reserva perdida manda conferir, nunca tentar de novo", () => {
  // Achado da revisão hostil: se a reserva se perde depois do POST, a tarefa pode
  // existir. "Tente de novo" criaria o segundo resumão da mesma leitura.
  const msg = mensagemDeTerminoFalho("book_reserva_perdida");
  assert.match(msg, /recarregue a estante/);
  // Nenhuma variação de "de novo": a frase não pode empurrar o gesto que duplica.
  assert.doesNotMatch(msg, /de novo|novamente/i);
});


// --- resolver uma obra presa: o catch era nu -------------------------------
// Ele dizia "a obra segue reservada" para os QUATRO desfechos, inclusive os três
// 409 que significam o contrário (a reserva já saiu). Mandar tentar de novo era
// mandar bater num endpoint que responderia 409 para sempre.

test("os 409 NÃO dizem que a obra segue reservada", () => {
  for (const detalhe of ["book_nao_esta_terminando", "book_reserva_perdida", "book_nao_encontrado"]) {
    const msg = mensagemDeResolucaoFalha(detalhe);
    assert.ok(
      !msg.includes("segue reservada"),
      `${detalhe} significa que a reserva saiu, e a frase mandava esperar: ${msg}`,
    );
  }
});

test("só a falha de conversa com o ClickUp mantém a obra reservada", () => {
  // É o único desfecho em que ela CONTINUA presa, e o único que pode pedir paciência.
  assert.match(mensagemDeResolucaoFalha("book_resumao_indisponivel"), /segue reservada/);
  assert.match(mensagemDeResolucaoFalha(null), /segue reservada/);
});

test("os desfechos que mexeram no estado pedem recarga da estante", () => {
  // Sem recarregar, a linha continua ali oferecendo "resolver" para sempre.
  assert.equal(resolucaoMudouEstado("book_nao_esta_terminando"), true);
  assert.equal(resolucaoMudouEstado("book_reserva_perdida"), true);
  assert.equal(resolucaoMudouEstado("book_nao_encontrado"), true);
  assert.equal(resolucaoMudouEstado("book_resumao_indisponivel"), false);
  assert.equal(resolucaoMudouEstado(null), false);
});

test("toda resolução falha produz uma frase, e nenhuma é código de servidor", () => {
  for (const d of ["book_nao_esta_terminando", "book_reserva_perdida", "book_nao_encontrado",
                   "book_resumao_indisponivel", null, "coisa_nova_do_servidor"]) {
    const msg = mensagemDeResolucaoFalha(d);
    assert.ok(msg.length > 0);
    assert.ok(!msg.includes("_"), `vazou código cru do servidor: ${msg}`);
  }
});
