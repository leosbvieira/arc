import * as SecureStore from "./storage";
import { capture, logSession } from "./api";

const IDX = "oq_idx_v2"; // indice da fila: [{id, chunks}] — so metadados, nunca conteudo
// Limite do SecureStore e em BYTES (~2048). Fatiamos por CARACTERES no pior caso UTF-8:
// 600 code units * 3 bytes/unit max = 1800 bytes <= limite, para qualquer emoji/acento.
// Invariante: CHUNK_CHARS >= 2 — o recuo de 1 char na fronteira de surrogate pair
// nunca pode zerar o avanco do loop de splitChunks (senao entra em loop infinito).
const CHUNK_CHARS = 600;

export type QueuedItem = {
  kind: "capture" | "session";
  payload: any;
  ts: number;
};

type IdxEntry = { id: string; chunks: number };

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
  } else {
    await logSession(it.payload);
  }
}

/** Reenvia em ordem; para no primeiro erro de REDE. Item envenenado e descartado (nunca
 * trava a fila). Tudo criptografado em repouso. */
async function _flush(): Promise<number> {
  let idx = await readIdx();
  while (idx.length > 0) {
    const entry = idx[0];
    let item: QueuedItem;
    try {
      item = await readItem(entry);
    } catch {
      // Item envenenado (JSON corrompido / chunks ausentes): o conteudo ja se perdeu.
      // De-indexa e descarta pra nao travar o resto da fila (fantasma preso = pior pra lei 1).
      idx = idx.slice(1);
      await writeIdx(idx); // de-indexa ANTES de apagar (orfao inofensivo > fantasma)
      await deleteItem(entry);
      continue;
    }
    try {
      await sendOne(item);
    } catch {
      break; // erro de rede: para e tenta de novo depois (rede continua ruim)
    }
    idx = idx.slice(1);
    await writeIdx(idx); // de-indexa ANTES de apagar os chunks (orfao > fantasma)
    await deleteItem(entry);
  }
  return idx.length;
}

export function flush(): Promise<number> {
  return serialized(() => _flush());
}
