import assert from "node:assert/strict";
import test from "node:test";

import { POINTS } from "../src/theme.ts";
import { montarMesa, valorDaAcao } from "../src/mesaView.ts";

// O teste importa o POINTS de produção e passa por parâmetro — os valores de
// verdade ficam presos ao teste, e o módulo puro não tem nenhum import de valor.

// Mesma tabela de horários de DEFAULT_PARAMS.ritos — o teste é quem importa a
// tabela real, o mesaView não sabe de onde ela veio.
const RITOS = [
  { slug: "toque", hora: "05:30", dia: null },
  { slug: "checkin", hora: "08:20", dia: null },
  { slug: "jornal", hora: "08:30", dia: null },
  { slug: "digest", hora: "09:00", dia: null },
  { slug: "shutdown", hora: "19:00", dia: null },
  { slug: "closing", hora: "21:00", dia: null },
  { slug: "review", hora: "20:00", dia: "domingo" },
];

const TODOS_OS_DESTINOS = [
  "agenda",
  "abertura",
  "triagem",
  "rotinas",
  "habitos",
  "revisao",
  "edificacao",
  "melhorias",
  "shutdown",
  "fechar",
  "settings",
];

function sinais(over = {}) {
  return {
    triagem: null,
    anki: null,
    leituras: null,
    aberturaFeita: null,
    shutdownFeito: null,
    ritmos: null,
    ...over,
  };
}

function destinos(grupos) {
  return grupos.flatMap((g) => g.itens.map((i) => i.destino));
}

function grupo(grupos, titulo) {
  return grupos.find((g) => g.titulo === titulo);
}

function item(grupos, destino) {
  return grupos.flatMap((g) => g.itens).find((i) => i.destino === destino);
}

// ---- CRITÉRIO DE ACEITE DURO: nenhum destino órfão, em qualquer combinação ----

test("anti-órfão: os 11 destinos da grade antiga existem em QUALQUER combinação de sinais", () => {
  const triagens = [null, { n: 0, maisVelhoD: null }, { n: 3, maisVelhoD: 4 }, { n: 1, maisVelhoD: null }, { n: -1, maisVelhoD: null }];
  const ankis = [null, 0, 4, -1];
  const leituras = [null, 0, 2];
  const aberturas = [null, false, true];
  const shutdowns = [null, false, true];
  const ritmos = [null, { feitos: 0, total: 0 }, { feitos: 2, total: 8 }, { feitos: 8, total: 8 }];

  let combinacoes = 0;
  for (const triagem of triagens)
    for (const anki of ankis)
      for (const leitura of leituras)
        for (const aberturaFeita of aberturas)
          for (const shutdownFeito of shutdowns)
            for (const ritmo of ritmos) {
              combinacoes += 1;
              const grupos = montarMesa(
                sinais({ triagem, anki, leituras: leitura, aberturaFeita, shutdownFeito, ritmos: ritmo }),
                POINTS,
                RITOS,
              );
              const ds = destinos(grupos);
              for (const d of TODOS_OS_DESTINOS) {
                assert.ok(
                  ds.includes(d),
                  `destino "${d}" sumiu em ${JSON.stringify({ triagem, anki, leitura, aberturaFeita, shutdownFeito, ritmo })}`,
                );
              }
              // Nenhum destino duplicado entre grupos.
              assert.equal(
                new Set(ds).size,
                ds.length,
                `destino duplicado em ${JSON.stringify({ triagem, anki, leitura, aberturaFeita, shutdownFeito, ritmo })}: ${ds}`,
              );
              // Grupo vazio não aparece.
              for (const g of grupos) assert.ok(g.itens.length > 0, `grupo "${g.titulo}" vazio`);
            }
  assert.equal(combinacoes, 5 * 4 * 3 * 3 * 3 * 4);
});

// ---- Ordem estável dos grupos e dos itens ----

test("ordem dos grupos: PRECISA DE VOCÊ, ROTINA DO DIA, ARQUIVO", () => {
  const grupos = montarMesa(
    sinais({
      triagem: { n: 2, maisVelhoD: 1 },
      anki: 3,
      leituras: 1,
      aberturaFeita: true,
      shutdownFeito: false,
      ritmos: { feitos: 2, total: 8 },
    }),
    POINTS,
    RITOS,
  );

  assert.deepEqual(
    grupos.map((g) => g.titulo),
    ["PRECISA DE VOCÊ", "ROTINA DO DIA", "ARQUIVO"],
  );
  assert.deepEqual(
    grupo(grupos, "PRECISA DE VOCÊ").itens.map((i) => i.destino),
    ["triagem", "revisao", "leitura", "shutdown", "fechar"],
  );
  assert.deepEqual(
    grupo(grupos, "ROTINA DO DIA").itens.map((i) => i.destino),
    ["abertura", "rotinas"],
  );
  assert.deepEqual(
    grupo(grupos, "ARQUIVO").itens.map((i) => i.destino),
    ["agenda", "habitos", "edificacao", "melhorias", "settings"],
  );
});

// ---- PRECISA DE VOCÊ ----

test("triagem com fila entra em precisa, com o mais velho no sub", () => {
  const grupos = montarMesa(sinais({ triagem: { n: 3, maisVelhoD: 5 } }), POINTS, RITOS);
  const t = item(grupos, "triagem");

  assert.equal(grupo(grupos, "PRECISA DE VOCÊ").itens.includes(t), true);
  assert.equal(t.nome, "Triagem");
  assert.equal(t.sub, "mais velho há 5d");
  assert.equal(t.contador, "3");
  assert.equal(t.feito, false);
});

test("triagem sem idade conhecida cai para o plural de itens parados", () => {
  const grupos = montarMesa(sinais({ triagem: { n: 1, maisVelhoD: null } }), POINTS, RITOS);
  assert.equal(item(grupos, "triagem").sub, "1 item parado");

  const grupos2 = montarMesa(sinais({ triagem: { n: 2, maisVelhoD: null } }), POINTS, RITOS);
  assert.equal(item(grupos2, "triagem").sub, "2 itens parados");
});

test("revisão entra em precisa com plural correto", () => {
  const um = montarMesa(sinais({ anki: 1 }), POINTS, RITOS);
  assert.equal(item(um, "revisao").sub, "1 cartão anki sugerido");
  assert.equal(item(um, "revisao").contador, "1");

  const quatro = montarMesa(sinais({ anki: 4 }), POINTS, RITOS);
  assert.equal(item(quatro, "revisao").sub, "4 cartões anki sugeridos");
});

test("leituras entram em precisa com plural correto", () => {
  const um = montarMesa(sinais({ leituras: 1 }), POINTS, RITOS);
  assert.equal(item(um, "leitura").sub, "1 sessão por fechar");
  assert.equal(item(um, "leitura").contador, "1");

  const duas = montarMesa(sinais({ leituras: 2 }), POINTS, RITOS);
  assert.equal(item(duas, "leitura").sub, "2 sessões por fechar");
});

test("shutdown não feito entra em precisa; fechar o dia está sempre lá, sem FEITO", () => {
  const grupos = montarMesa(sinais({ shutdownFeito: false }), POINTS, RITOS);
  const shutdown = item(grupos, "shutdown");
  const fechar = item(grupos, "fechar");

  assert.equal(grupo(grupos, "PRECISA DE VOCÊ").itens.includes(shutdown), true);
  assert.equal(shutdown.sub, "rito das 19h · fecha o trabalho");
  assert.equal(shutdown.contador, "19h");

  assert.equal(grupo(grupos, "PRECISA DE VOCÊ").itens.includes(fechar), true);
  assert.equal(fechar.sub, `rito das 21h · vale +${POINTS.fechamento}`);
  assert.equal(fechar.contador, "21h");
  // Não existe flag de fechamento feito no BFF: nunca FEITO ✓.
  assert.equal(fechar.feito, false);
});

// ---- ROTINA DO DIA ----

test("abertura feita e não feita: sub e feito mudam juntos", () => {
  const feita = montarMesa(sinais({ aberturaFeita: true }), POINTS, RITOS);
  const abFeita = item(feita, "abertura");
  assert.equal(grupo(feita, "ROTINA DO DIA").itens.includes(abFeita), true);
  assert.equal(abFeita.sub, "check-in do dia feito");
  assert.equal(abFeita.feito, true);

  const naoFeita = montarMesa(sinais({ aberturaFeita: false }), POINTS, RITOS);
  const abNao = item(naoFeita, "abertura");
  assert.equal(abNao.sub, "o dia ainda não foi aberto");
  assert.equal(abNao.feito, false);
});

test("shutdown feito sai de precisa e aparece na rotina como FEITO", () => {
  const grupos = montarMesa(sinais({ shutdownFeito: true }), POINTS, RITOS);
  const s = item(grupos, "shutdown");

  assert.equal(grupo(grupos, "ROTINA DO DIA").itens.includes(s), true);
  assert.equal(s.sub, "trabalho fechado");
  assert.equal(s.feito, true);
  assert.equal(grupo(grupos, "PRECISA DE VOCÊ").itens.includes(s), false);
});

test("ritmos conhecidos mostram N de M e feito só quando completo", () => {
  const parcial = montarMesa(sinais({ ritmos: { feitos: 2, total: 8 } }), POINTS, RITOS);
  const r = item(parcial, "rotinas");
  assert.equal(r.sub, "2 de 8 hoje");
  assert.equal(r.contador, "2/8");
  assert.equal(r.feito, false);

  const completo = montarMesa(sinais({ ritmos: { feitos: 8, total: 8 } }), POINTS, RITOS);
  assert.equal(item(completo, "rotinas").feito, true);

  // 0 de 0 não é "feito" — não há ritmo configurado.
  const vazio = montarMesa(sinais({ ritmos: { feitos: 0, total: 0 } }), POINTS, RITOS);
  assert.equal(item(vazio, "rotinas").feito, false);
});

// ---- ARQUIVO ----

test("tudo zerado: filas vazias caem no arquivo com sub fixo, sem número", () => {
  const grupos = montarMesa(
    sinais({
      triagem: { n: 0, maisVelhoD: null },
      anki: 0,
      leituras: 0,
      aberturaFeita: false,
      shutdownFeito: false,
      ritmos: { feitos: 1, total: 4 },
    }),
    POINTS,
    RITOS,
  );
  const arquivo = grupo(grupos, "ARQUIVO");

  assert.deepEqual(
    arquivo.itens.map((i) => i.destino),
    ["agenda", "triagem", "revisao", "habitos", "edificacao", "melhorias", "settings"],
  );
  assert.equal(item(grupos, "triagem").sub, "a fila de entrada");
  assert.equal(item(grupos, "triagem").contador, null);
  assert.equal(item(grupos, "revisao").sub, "cartões e revisão");
  // Leituras zeradas somem da mesa (não havia botão de leitura na grade antiga).
  assert.equal(item(grupos, "leitura"), undefined);
});

test("sinal desconhecido (null) manda o item para o arquivo, sem mentir estado", () => {
  const grupos = montarMesa(sinais(), POINTS, RITOS);
  const arquivo = grupo(grupos, "ARQUIVO");

  assert.deepEqual(
    arquivo.itens.map((i) => i.destino),
    ["agenda", "triagem", "revisao", "habitos", "edificacao", "melhorias", "rotinas", "abertura", "shutdown", "settings"],
  );
  assert.equal(item(grupos, "abertura").sub, "abrir o dia");
  assert.equal(item(grupos, "shutdown").sub, "fechar o trabalho");
  assert.equal(item(grupos, "rotinas").sub, "os ritmos do dia");
  assert.equal(item(grupos, "agenda").sub, "semana e horários");
  assert.equal(item(grupos, "habitos").sub, "hábitos a reduzir");
  assert.equal(item(grupos, "edificacao").sub, "projetos de longo prazo");
  assert.equal(item(grupos, "melhorias").sub, "a fila de melhorias");
  assert.equal(item(grupos, "settings").sub, "ajustes do app");
  // Sem ROTINA DO DIA: grupo vazio não aparece.
  assert.equal(grupo(grupos, "ROTINA DO DIA"), undefined);
  // Arquivo nunca tem contador nem feito.
  for (const i of arquivo.itens) {
    assert.equal(i.contador, null);
    assert.equal(i.feito, false);
  }
});

test("a hora exibida vem da tabela, não de literal", () => {
  const ritos = [
    { slug: "shutdown", hora: "18:00", dia: null },
    { slug: "closing", hora: "22:00", dia: null },
  ];
  const grupos = montarMesa(sinais({ shutdownFeito: false }), POINTS, ritos);
  assert.equal(item(grupos, "shutdown").contador, "18h");
  assert.equal(item(grupos, "fechar").contador, "22h");
  assert.match(item(grupos, "shutdown").sub, /18h/);
});

// ---- valorDaAcao (preço do hero da Home) ----

test("valorDaAcao mapeia o target do hero para a tabela POINTS", () => {
  assert.equal(valorDaAcao("fechar", POINTS), POINTS.fechamento);
  assert.equal(valorDaAcao("shutdown", POINTS), POINTS.shutdown);
  assert.equal(valorDaAcao("rotinas", POINTS), POINTS.rotina);
  assert.equal(valorDaAcao("abertura", POINTS), POINTS.rotina);
  assert.equal(valorDaAcao("capturar", POINTS), POINTS.captura);
  assert.equal(valorDaAcao("leitura", POINTS), POINTS.captura);
  assert.equal(valorDaAcao("tarefas", POINTS), POINTS.tarefa);
});

test("valorDaAcao devolve null para o que não tem preço — a tela não desenha nada", () => {
  for (const target of ["revisao", "triagem", "agenda", "habitos", "settings", "qualquer-coisa"]) {
    assert.equal(valorDaAcao(target, POINTS), null);
  }
});
