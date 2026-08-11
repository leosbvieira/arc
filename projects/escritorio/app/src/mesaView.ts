// A Mesa é ordenação e agrupamento — lógica pura, sem import de valor (o Node
// tira os tipos sozinho, mas não resolve import relativo em runtime). A tabela
// de pontos entra por parâmetro; o teste é quem importa o POINTS de produção.

// Estrutural, sem `despejoBonus`: o POINTS real de theme.ts é atribuível a ela.
export type PointsTable = { tarefa: number; rotina: number; captura: number; fechamento: number; shutdown: number };

// A hora entra por parâmetro, pelo mesmo motivo que a tabela de pontos: o
// mesaView escrevia "19h" e "21h" à mão, e mudar o rito deixava a Mesa mentindo.
export type Rito = { slug: string; hora: string; dia: string | null };

function horaCurta(ritos: Rito[], slug: string): string {
  const r = ritos.find((x) => x.slug === slug);
  if (!r) return "";
  const [h, m] = r.hora.split(":");
  return m === "00" ? `${Number(h)}h` : `${Number(h)}h${m}`;
}

// O que a tela conseguiu carregar. null = NÃO CARREGOU, e null nunca vira estado:
// sinal desconhecido manda o item para o arquivo, sem número inventado.
export type MesaSinais = {
  triagem: { n: number; maisVelhoD: number | null } | null;
  anki: number | null;
  leituras: number | null;
  aberturaFeita: boolean | null;
  shutdownFeito: boolean | null;
  ritmos: { feitos: number; total: number } | null;
};

export type MesaItem = {
  destino: string; // o que vai para openDestination()
  nome: string;
  sub: string;
  contador: string | null; // texto curto à direita ("3", "5/8", "21h") ou null
  feito: boolean; // true → a tela desenha "FEITO ✓" em sálvia no lugar do contador
};

export type MesaGrupo = { titulo: string; itens: MesaItem[] };

function item(destino: string, nome: string, sub: string, contador: string | null = null, feito = false): MesaItem {
  return { destino, nome, sub, contador, feito };
}

export function montarMesa(sinais: MesaSinais, points: PointsTable, ritos: Rito[]): MesaGrupo[] {
  const precisa: MesaItem[] = [];
  const rotina: MesaItem[] = [];
  const arquivo: MesaItem[] = [];

  // Uma decisão por item, usada nos DOIS lados (precisa e arquivo). Antes eram
  // duas condições escritas em separado que por acaso se completavam: se o BFF
  // mandasse n negativo, as duas seriam falsas juntas e o item sumia da Mesa —
  // e sem a grade "Ferramentas" (apagada na 3a) a tela ficaria inalcançável.
  const triagemNaFila = !!sinais.triagem && sinais.triagem.n > 0;
  const ankiNaFila = sinais.anki !== null && sinais.anki > 0;
  const leiturasNaFila = sinais.leituras !== null && sinais.leituras > 0;

  // PRECISA DE VOCÊ — só entra quem tem trabalho parado agora.
  if (triagemNaFila) {
    const { n, maisVelhoD } = sinais.triagem!;
    precisa.push(item(
      "triagem", "Triagem",
      maisVelhoD !== null ? `mais velho há ${maisVelhoD}d` : n === 1 ? "1 item parado" : `${n} itens parados`,
      String(n),
    ));
  }
  if (ankiNaFila) {
    precisa.push(item(
      "revisao", "Revisão",
      `${sinais.anki} cart${sinais.anki === 1 ? "ão" : "ões"} anki sugerido${sinais.anki === 1 ? "" : "s"}`,
      String(sinais.anki),
    ));
  }
  if (leiturasNaFila) {
    precisa.push(item(
      "leitura", "Leituras",
      `${sinais.leituras} ${sinais.leituras === 1 ? "sessão" : "sessões"} por fechar`,
      String(sinais.leituras),
    ));
  }
  if (sinais.shutdownFeito === false) {
    const h = horaCurta(ritos, "shutdown");
    precisa.push(item("shutdown", "Shutdown", `rito das ${h} · fecha o trabalho`, h));
  }
  // Não existe flag de "fechamento feito" no BFF: Fechar o dia fica sempre aqui,
  // com a hora e o valor — e nunca com FEITO ✓.
  const hFechar = horaCurta(ritos, "closing");
  precisa.push(item("fechar", "Fechar o dia", `rito das ${hFechar} · vale +${points.fechamento}`, hFechar));

  // ROTINA DO DIA — o que tem estado conhecido.
  if (sinais.aberturaFeita !== null) {
    rotina.push(item(
      "abertura", "Abertura",
      sinais.aberturaFeita ? "check-in do dia feito" : "o dia ainda não foi aberto",
      null,
      sinais.aberturaFeita,
    ));
  }
  if (sinais.shutdownFeito === true) {
    rotina.push(item("shutdown", "Shutdown", "trabalho fechado", null, true));
  }
  if (sinais.ritmos !== null) {
    const { feitos, total } = sinais.ritmos;
    rotina.push(item(
      "rotinas", "Ritmos",
      `${feitos} de ${total} hoje`,
      `${feitos}/${total}`,
      feitos === total && total > 0,
    ));
  }

  // ARQUIVO — o resto, sempre presente, sempre nesta ordem.
  arquivo.push(item("agenda", "Agenda", "semana e horários"));
  if (!triagemNaFila) {
    arquivo.push(item("triagem", "Triagem", "a fila de entrada"));
  }
  if (!ankiNaFila) {
    arquivo.push(item("revisao", "Revisão", "cartões e revisão"));
  }
  arquivo.push(item("habitos", "Reduzir", "hábitos a reduzir"));
  arquivo.push(item("edificacao", "Edificação", "projetos de longo prazo"));
  arquivo.push(item("melhorias", "Melhorias", "a fila de melhorias"));
  if (sinais.ritmos === null) {
    arquivo.push(item("rotinas", "Ritmos", "os ritmos do dia"));
  }
  if (sinais.aberturaFeita === null) {
    arquivo.push(item("abertura", "Abertura", "abrir o dia"));
  }
  if (sinais.shutdownFeito === null) {
    arquivo.push(item("shutdown", "Shutdown", "fechar o trabalho"));
  }
  arquivo.push(item("settings", "Ajustes", "ajustes do app"));

  // Grupo vazio não aparece.
  return [
    { titulo: "PRECISA DE VOCÊ", itens: precisa },
    { titulo: "ROTINA DO DIA", itens: rotina },
    { titulo: "ARQUIVO", itens: arquivo },
  ].filter((g) => g.itens.length > 0);
}

// Preço do hero da Home: mapeia o action.target do actionForAt() para a tabela
// POINTS (provisória, display-only). null = sem preço, e a tela não desenha nada.
export function valorDaAcao(target: string, points: PointsTable): number | null {
  switch (target) {
    case "fechar":
      return points.fechamento;
    case "shutdown":
      return points.shutdown;
    case "rotinas":
    case "abertura":
      return points.rotina;
    case "capturar":
    case "leitura":
      return points.captura;
    case "tarefas":
      return points.tarefa;
    default:
      return null;
  }
}
