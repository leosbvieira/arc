// Agrupamento da fila de melhorias. Puro de propósito: é a regra que decide o
// que o Leo vê primeiro, e a tela só desenha o resultado.
//
// A ordem importa mais aqui do que em outras telas. Ele é procrastinador por
// autodeclaração: se a fila abrir com 30 itens indistintos, ele fecha. Então o
// topo é sempre "a da semana" (uma decisão já tomada) e logo abaixo "a triar"
// (um toque cada), e só depois o resto.
//
// Este módulo é o dono do vocabulário de alvo — `api.ts` reexporta daqui. O
// caminho contrário criaria import de VALOR a partir de api.ts, que arrasta
// react-native e impede o `node --test` de carregar o módulo.

export const ALVOS_MELHORIA = ["app", "empresa", "fluxo"] as const;

export type AlvoMelhoria = (typeof ALVOS_MELHORIA)[number];

/** O mínimo que o agrupamento precisa; a tela continua usando o tipo completo. */
export type MelhoriaAgrupavel = {
  alvo: string | null;
  status: string;
  criado: number;
  escolhida_em: number | null;
  escolhida_semana: string | null;
};

export type GruposMelhoria<T> = {
  escolhida: T | null;
  /** Escolhas de semanas anteriores ainda em aberto: viram a pergunta "fez?". */
  vencidas: T[];
  aTriar: T[];
  porAlvo: Record<AlvoMelhoria, T[]>;
  resolvidas: T[];
};

function maisRecentePrimeiro(a: MelhoriaAgrupavel, b: MelhoriaAgrupavel): number {
  return b.criado - a.criado;
}

function ehAlvoConhecido(alvo: string | null): alvo is AlvoMelhoria {
  return alvo !== null && (ALVOS_MELHORIA as readonly string[]).includes(alvo);
}

export function agruparMelhorias<T extends MelhoriaAgrupavel>(
  itens: T[],
  /** Semana ISO corrente, vinda do servidor junto com a lista. Sem recalcular
   *  data no cliente: é exatamente onde este projeto já se queimou com fuso. */
  semanaAtual?: string | null,
): GruposMelhoria<T> {
  const porAlvo: Record<AlvoMelhoria, T[]> = { app: [], empresa: [], fluxo: [] };
  const aTriar: T[] = [];
  const resolvidas: T[] = [];
  const escolhidas: T[] = [];
  const vencidas: T[] = [];

  // Alvo desconhecido (BFF mais novo que o APK) cai na triagem em vez de sumir:
  // item invisível é item perdido, e a lei 1 vale para a fila também.
  const enfileirar = (item: T) => {
    if (ehAlvoConhecido(item.alvo)) porAlvo[item.alvo].push(item);
    else aTriar.push(item);
  };

  for (const item of itens) {
    if (item.status === "feita" || item.status === "descartada") resolvidas.push(item);
    // A escolha de outra semana não é "a desta semana". Sem o servidor dizer qual
    // é a semana atual (APK novo + BFF antigo) não dá para decidir: acusar uma
    // escolha legítima de vencida seria pior, então ela segue no grupo de cima e
    // a tela mostra a semana do próprio item no cabeçalho.
    else if (item.status === "escolhida") {
      const deOutraSemana =
        !!semanaAtual && !!item.escolhida_semana && item.escolhida_semana !== semanaAtual;
      (deOutraSemana ? vencidas : escolhidas).push(item);
    } else enfileirar(item);
  }

  // O servidor garante uma escolhida só, mas uma corrida entre dois aparelhos
  // pode entregar duas na mesma resposta. Duas "da semana" valem tanto quanto
  // nenhuma, então a mais recente vence e as outras voltam para a fila.
  escolhidas.sort((a, b) => (b.escolhida_em ?? 0) - (a.escolhida_em ?? 0));
  const [escolhida, ...perdedoras] = escolhidas;
  perdedoras.forEach(enfileirar);

  vencidas.sort((a, b) => (b.escolhida_em ?? 0) - (a.escolhida_em ?? 0));
  aTriar.sort(maisRecentePrimeiro);
  resolvidas.sort(maisRecentePrimeiro);
  for (const alvo of ALVOS_MELHORIA) porAlvo[alvo].sort(maisRecentePrimeiro);

  return { escolhida: escolhida ?? null, vencidas, aTriar, porAlvo, resolvidas };
}
