import * as SecureStore from "expo-secure-store";
import { capture } from "./api";

const IDX = "oq_idx_v2";   // indice da fila: [{id, chunks}] — so metadados, nunca conteudo
// Limite do SecureStore e em BYTES (~2048). Fatiamos por CARACTERES no pior caso UTF-8:
// 600 code units * 3 bytes/unit max = 1800 bytes <= limite, para qualquer emoji/acento.
const CHUNK_CHARS = 600;

export type QueuedItem = { kind: "capture" | "session"; payload: any; ts: number };

type IdxEntry = { id: string; chunks: number };

async function readIdx(): Promise<IdxEntry[]> {
  const raw = await SecureStore.getItemAsync(IDX);
  return raw ? (JSON.parse(raw) as IdxEntry[]) : [];
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

export async function enqueue(item: QueuedItem): Promise<void> {
  const parts = splitChunks(JSON.stringify(item));
  const id = `${item.ts}_${Math.random().toString(36).slice(2, 8)}`;
  for (let i = 0; i < parts.length; i++) {
    await SecureStore.setItemAsync(`oq_${id}_${i}`, parts[i]);
  }
  await writeIdx([...(await readIdx()), { id, chunks: parts.length }]);  // indice por ultimo: item orfao > item perdido
}

export async function pendingCount(): Promise<number> {
  return (await readIdx()).length;
}

async function sendOne(it: QueuedItem): Promise<void> {
  if (it.kind === "capture") await capture(it.payload.text, it.payload.profile);
  else throw new Error("kind não suportado"); // kind "session" chega na Task 15
}

/** Reenvia em ordem; para no primeiro erro (rede continua ruim). Tudo criptografado em repouso. */
export async function flush(): Promise<number> {
  let idx = await readIdx();
  while (idx.length > 0) {
    try {
      await sendOne(await readItem(idx[0]));
      await deleteItem(idx[0]);
      idx = idx.slice(1);
      await writeIdx(idx);
    } catch {
      break;
    }
  }
  return idx.length;
}
