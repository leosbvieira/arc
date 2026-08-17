import * as SecureStore from "./storage";
import { capture, completeTask, logSession } from "./api";
import { decidirAposFalha, paraAFila } from "./offlineError";
import { ResultadoDoFlush, drenar } from "./filaDrenagem";

const IDX = "oq_idx_v2"; // indice da fila: [{id, chunks}] — so metadados, nunca conteudo
// Escaninho dos recusados: item que o servidor rejeitou MAX_TENTATIVAS vezes sai da
// fila (senao trava todo mundo atras dele) mas NAO e apagado — "nada se perde" vale
// tambem pro que falhou. Os chunks continuam onde estao; so o indice muda.
const IDX_REJEITADOS = "oq_rejeitados_v1";
// Limite do SecureStore e em BYTES (~2048). Fatiamos por CARACTERES no pior caso UTF-8:
// 600 code units * 3 bytes/unit max = 1800 bytes <= limite, para qualquer emoji/acento.
// Invariante: CHUNK_CHARS >= 2 — o recuo de 1 char na fronteira de surrogate pair
// nunca pode zerar o avanco do loop de splitChunks (senao entra em loop infinito).
const CHUNK_CHARS = 600;

export type QueuedItem = {
  // `complete` entrou depois: a garantia "nada se perde" cobria a CAPTURA e deixava a
  // EXECUÇÃO de fora — concluir no metrô mostrava um alerta e a ação evaporava.
  kind: "capture" | "session" | "complete";
  payload: any;
  ts: number;
};

// `tentativas` mora no INDICE, nao no item: o indice e metadado pequeno e reescrito
// a cada passo de qualquer jeito, entao contar aqui evita re-fatiar e regravar os
// chunks do conteudo a cada recusa — que seria escrita cara e uma chance a mais de
// corromper justamente o item que ja esta com problema.
type IdxEntry = { id: string; chunks: number; tentativas?: number };

function idForTimestamp(ts: number): string {
  return `${ts}_${Math.random().toString(36).slice(2, 8)}`;
}

/** Chave estável de uma tentativa de captura. Deve ser criada antes do primeiro
 * POST e reaproveitada se a mesma tentativa precisar entrar na fila offline. */
export function createCaptureClientKey(ts: number = Date.now()): string {
  return idForTimestamp(ts);
}

// Mutex async (promise-chain, sem dependencia nova): serializa TODA operacao que muta
// o indice (enqueue/flush). Fecha os dois interleavings: dois flush nao rodam sobrepostos
// (sem envio duplicado) e um enqueue no meio de um flush nao perde/envenena o indice.
let lock: Promise<unknown> = Promise.resolve();

function serialized<T>(op: () => Promise<T>): Promise<T> {
  const run = lock.then(op, op);
  lock = run.catch(() => {});
  return run;
}

async function readIdx(): Promise<IdxEntry[]> {
  const raw = await SecureStore.getItemAsync(IDX);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as IdxEntry[];
  } catch {
    return []; // indice corrompido: recomeca (os chunks viram orfaos inofensivos)
  }
}

async function writeIdx(idx: IdxEntry[]): Promise<void> {
  await SecureStore.setItemAsync(IDX, JSON.stringify(idx));
}

async function readItem(e: IdxEntry): Promise<QueuedItem> {
  let s = "";
  for (let i = 0; i < e.chunks; i++) {
    s += (await SecureStore.getItemAsync(`oq_${e.id}_${i}`)) ?? "";
  }
  return JSON.parse(s) as QueuedItem;
}

async function deleteItem(e: IdxEntry): Promise<void> {
  for (let i = 0; i < e.chunks; i++) {
    await SecureStore.deleteItemAsync(`oq_${e.id}_${i}`);
  }
}

function splitChunks(s: string): string[] {
  const out: string[] = [];
  let start = 0;
  while (start < s.length) {
    let end = Math.min(start + CHUNK_CHARS, s.length);
    // nunca partir um surrogate pair (emoji) na fronteira do chunk
    if (end < s.length) {
      const code = s.charCodeAt(end - 1);
      if (code >= 0xd800 && code <= 0xdbff) end -= 1;
    }
    out.push(s.slice(start, end));
    start = end;
  }
  return out.length ? out : [""];
}

async function _enqueue(item: QueuedItem): Promise<void> {
  const id = idForTimestamp(item.ts);
  const storedItem: QueuedItem =
    item.kind === "capture"
      ? {
          ...item,
          payload: {
            ...item.payload,
            client_key: item.payload?.client_key ?? id,
          },
        }
      : item;
  const parts = splitChunks(JSON.stringify(storedItem));

  for (let i = 0; i < parts.length; i++) {
    await SecureStore.setItemAsync(`oq_${id}_${i}`, parts[i]);
  }
  await writeIdx([
    ...(await readIdx()),
    { id, chunks: parts.length },
  ]); // indice por ultimo: item orfao > item perdido
}

export function enqueue(item: QueuedItem): Promise<void> {
  return serialized(() => _enqueue(item));
}

export async function pendingCount(): Promise<number> {
  return (await readIdx()).length;
}

async function sendOne(it: QueuedItem): Promise<void> {
  if (it.kind === "capture") {
    await capture(
      it.payload.text,
      it.payload.profile,
      it.payload.client_key,
      Boolean(it.payload.sensivel),
    );
  } else if (it.kind === "complete") {
    await completeTask(it.payload.id);
  } else {
    await logSession(it.payload);
  }
}

export type { ResultadoDoFlush } from "./filaDrenagem";

/** Reenvia em ordem. O LAÇO mora em `filaDrenagem.ts`, sem import nenhum, pra poder
 * ser testado: este arquivo importa expo-secure-store e nunca sobe no `node --test`,
 * e foi essa impossibilidade que deixou o `catch { break }` viver a vida inteira do
 * arquivo. Aqui fica só a fiação com o aparelho. */
async function _flush(): Promise<ResultadoDoFlush> {
  return drenar<QueuedItem>({
    lerIndice: readIdx,
    gravarIndice: writeIdx,
    lerItem: readItem,
    apagarItem: deleteItem,
    enviar: sendOne,
    arquivarRejeitado,
    decidir: decidirAposFalha,
    paraAFila,
  });
}

async function arquivarRejeitado(entry: IdxEntry): Promise<void> {
  const raw = await SecureStore.getItemAsync(IDX_REJEITADOS);
  let atuais: IdxEntry[] = [];
  if (raw) {
    try {
      atuais = JSON.parse(raw) as IdxEntry[];
    } catch {
      atuais = [];
    }
  }
  await SecureStore.setItemAsync(
    IDX_REJEITADOS,
    JSON.stringify([...atuais, entry]),
  );
}

async function lerRejeitados(): Promise<IdxEntry[]> {
  const raw = await SecureStore.getItemAsync(IDX_REJEITADOS);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as IdxEntry[];
  } catch {
    return [];
  }
}

/** Quantos itens o servidor recusou vezes demais. Sao os que exigem o Leo — nenhum
 * retry automatico resolve — e por isso a tela precisa saber contar. */
export async function rejectedCount(): Promise<number> {
  return (await lerRejeitados()).length;
}

/** O TEXTO dos recusados, pra tela poder mostrar o que ficou pra tras.
 *
 * Sem isto o escaninho era so-de-escrita: os chunks ficavam gravados e NENHUM codigo
 * sabia le-los de volta. "Nada se perde" que ninguem consegue recuperar e perda com
 * outro nome — e o badge vermelho nao tinha como voltar a zero. */
export async function listRejected(): Promise<{ id: string; item: QueuedItem }[]> {
  const saida: { id: string; item: QueuedItem }[] = [];
  for (const entry of await lerRejeitados()) {
    try {
      saida.push({ id: entry.id, item: await readItem(entry) });
    } catch {
      // chunk sumiu: nao ha o que mostrar, e insistir travaria a lista inteira
    }
  }
  return saida;
}

/** Devolve os recusados pro fim da fila, com a contagem zerada. E o que faz sentido
 * depois de entrar de novo, ou depois de o servidor voltar ao normal. */
export function retryRejected(): Promise<number> {
  return serialized(async () => {
    const rejeitados = await lerRejeitados();
    if (!rejeitados.length) return 0;
    // Fila primeiro, escaninho depois: se morrer no meio, o item aparece nos dois
    // (a drenagem resolve) em vez de em nenhum.
    await writeIdx([
      ...(await readIdx()),
      ...rejeitados.map((e) => ({ id: e.id, chunks: e.chunks })),
    ]);
    await SecureStore.setItemAsync(IDX_REJEITADOS, "[]");
    return rejeitados.length;
  });
}

/** Descarta de vez. So o Leo pode mandar fazer isto: e a unica operacao do modulo
 * que destroi conteudo dele de proposito. */
export function discardRejected(): Promise<number> {
  return serialized(async () => {
    const rejeitados = await lerRejeitados();
    await SecureStore.setItemAsync(IDX_REJEITADOS, "[]");
    for (const entry of rejeitados) await deleteItem(entry);
    return rejeitados.length;
  });
}

export function flush(): Promise<ResultadoDoFlush> {
  return serialized(() => _flush());
}
