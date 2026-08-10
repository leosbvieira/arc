import * as SecureStore from "./storage";

import {
  joinSecureChunks,
  safeSessionKey,
  splitSecureChunks,
} from "./readingDraftCodec";
import { normalizeReadingActiveSeconds } from "./readingSessionState";

const META_KEY = "reading_draft_meta_v2";
const CHUNK_PREFIX = "reading_draft_chunk_v2_";
const ITEM_META_PREFIX = "reading_draft_item_meta_v2_";
const ITEM_CHUNK_PREFIX = "reading_draft_item_chunk_v2_";
const LEGACY_META_KEY = "reading_draft_meta_v1";
const LEGACY_CHUNK_PREFIX = "reading_draft_chunk_v1_";

export type ReadingDraftItem = {
  id: string;
  kind: string;
  text: string;
  anki?: boolean;
  seq: number;
};

export type ReadingDraft = {
  sessionKey: string;
  remoteId: number | null;
  book: string;
  bookId: number | null;
  pageStart: string;
  pageEnd: string;
  startedAt: number;
  activeSeconds: number;
  updatedAt: number;
  items: ReadingDraftItem[];
  syncedSeq: number;
  status: "active" | "pending";
};

type DraftMeta = {
  generation: string;
  chunks: number;
  sessionKey: string;
  itemCount: number;
};
type StoredDraft = Omit<ReadingDraft, "items"> & { itemCount: number };

let lock: Promise<unknown> = Promise.resolve();

function serialized<T>(operation: () => Promise<T>): Promise<T> {
  const current = lock.then(operation, operation);
  lock = current.catch(() => {});
  return current;
}

function chunkKey(generation: string, index: number): string {
  return `${CHUNK_PREFIX}${generation}_${index}`;
}

function itemKey(sessionKey: string, seq: number): string {
  return `${ITEM_META_PREFIX}${safeSessionKey(sessionKey)}_${seq}`;
}

function itemChunkKey(
  sessionKey: string,
  seq: number,
  index: number,
  generation?: string,
): string {
  const version = generation ? `${generation}_` : "";
  return `${ITEM_CHUNK_PREFIX}${safeSessionKey(sessionKey)}_${seq}_${version}${index}`;
}

async function writeItem(
  sessionKey: string,
  item: ReadingDraftItem,
): Promise<void> {
  const rawPrevious = await SecureStore.getItemAsync(itemKey(sessionKey, item.seq));
  let previous: { chunks?: number; generation?: string } | null = null;
  try {
    previous = rawPrevious ? JSON.parse(rawPrevious) : null;
  } catch {
    previous = null;
  }
  const chunks = splitSecureChunks(JSON.stringify(item));
  const generation = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  for (let i = 0; i < chunks.length; i += 1) {
    await SecureStore.setItemAsync(
      itemChunkKey(sessionKey, item.seq, i, generation),
      chunks[i],
    );
  }
  await SecureStore.setItemAsync(
    itemKey(sessionKey, item.seq),
    JSON.stringify({ chunks: chunks.length, generation }),
  );
  if (previous) {
    for (let i = 0; i < (previous.chunks ?? 0); i += 1) {
      await SecureStore.deleteItemAsync(
        itemChunkKey(sessionKey, item.seq, i, previous.generation),
      );
    }
  }
}

async function readItem(
  sessionKey: string,
  seq: number,
): Promise<ReadingDraftItem | null> {
  const rawMeta = await SecureStore.getItemAsync(itemKey(sessionKey, seq));
  if (!rawMeta) return null;
  const meta = JSON.parse(rawMeta) as { chunks?: number; generation?: string };
  if (!Number.isInteger(meta.chunks) || (meta.chunks ?? 0) < 1) return null;
  const chunks: string[] = [];
  for (let i = 0; i < meta.chunks!; i += 1) {
    const chunk = await SecureStore.getItemAsync(
      itemChunkKey(sessionKey, seq, i, meta.generation),
    );
    if (chunk === null) return null;
    chunks.push(chunk);
  }
  const item = JSON.parse(joinSecureChunks(chunks)) as ReadingDraftItem;
  return item.seq === seq && typeof item.text === "string" ? item : null;
}

async function deleteItem(sessionKey: string, seq: number): Promise<void> {
  const rawMeta = await SecureStore.getItemAsync(itemKey(sessionKey, seq));
  await SecureStore.deleteItemAsync(itemKey(sessionKey, seq));
  if (!rawMeta) return;
  try {
    const meta = JSON.parse(rawMeta) as { chunks?: number; generation?: string };
    for (let i = 0; i < (meta.chunks ?? 0); i += 1) {
      await SecureStore.deleteItemAsync(
        itemChunkKey(sessionKey, seq, i, meta.generation),
      );
    }
  } catch {
    // Meta corrompida ja foi de-indexada; chunks orfaos nao ficam acessiveis.
  }
}

async function readMeta(): Promise<DraftMeta | null> {
  const raw = await SecureStore.getItemAsync(META_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as DraftMeta;
    return typeof parsed.generation === "string" &&
      parsed.generation.length > 0 &&
      Number.isInteger(parsed.chunks) &&
      parsed.chunks > 0 &&
      typeof parsed.sessionKey === "string" &&
      Number.isInteger(parsed.itemCount) &&
      parsed.itemCount >= 0
      ? parsed
      : null;
  } catch {
    return null;
  }
}

export async function loadReadingDraft(): Promise<ReadingDraft | null> {
  const meta = await readMeta();
  if (!meta) return loadLegacyReadingDraft();
  const headerChunks: string[] = [];
  for (let i = 0; i < meta.chunks; i += 1) {
    const part = await SecureStore.getItemAsync(
      chunkKey(meta.generation, i),
    );
    if (part === null) return null;
    headerChunks.push(part);
  }
  try {
    const parsed = JSON.parse(
      joinSecureChunks(headerChunks),
    ) as Partial<StoredDraft>;
    if (
      typeof parsed.sessionKey !== "string" ||
      typeof parsed.startedAt !== "number" ||
      typeof parsed.updatedAt !== "number" ||
      typeof parsed.syncedSeq !== "number" ||
      parsed.sessionKey !== meta.sessionKey ||
      parsed.itemCount !== meta.itemCount ||
      (parsed.status !== "active" && parsed.status !== "pending")
    ) {
      return null;
    }
    const items: ReadingDraftItem[] = [];
    for (let seq = 1; seq <= meta.itemCount; seq += 1) {
      const item = await readItem(meta.sessionKey, seq);
      if (!item) return null;
      items.push(item);
    }
    const { itemCount: _itemCount, ...header } = parsed as StoredDraft;
    return {
      ...header,
      // Rascunho gravado antes da estante não tem bookId; `undefined` quebraria o
      // JSON do sync, então vira null explícito.
      bookId: header.bookId ?? null,
      activeSeconds: normalizeReadingActiveSeconds(
        (parsed as Partial<StoredDraft>).activeSeconds,
        parsed.startedAt,
        parsed.updatedAt,
      ),
      items,
    };
  } catch {
    return null;
  }
}

async function loadLegacyReadingDraft(): Promise<ReadingDraft | null> {
  const rawMeta = await SecureStore.getItemAsync(LEGACY_META_KEY);
  if (!rawMeta) return null;
  try {
    const meta = JSON.parse(rawMeta) as { generation: string; chunks: number };
    const chunks: string[] = [];
    for (let i = 0; i < meta.chunks; i += 1) {
      const chunk = await SecureStore.getItemAsync(
        `${LEGACY_CHUNK_PREFIX}${meta.generation}_${i}`,
      );
      if (chunk === null) return null;
      chunks.push(chunk);
    }
    const draft = JSON.parse(joinSecureChunks(chunks)) as ReadingDraft;
    if (!Array.isArray(draft.items) || typeof draft.sessionKey !== "string") {
      return null;
    }
    draft.activeSeconds = normalizeReadingActiveSeconds(
      draft.activeSeconds,
      draft.startedAt,
      draft.updatedAt,
    );
    // Rascunho legado não tem bookId; `undefined` quebraria o JSON do sync,
    // então vira null explícito (mesmo motivo do loadReadingDraft principal).
    draft.bookId = draft.bookId ?? null;
    await saveReadingDraft(draft);
    await SecureStore.deleteItemAsync(LEGACY_META_KEY);
    for (let i = 0; i < meta.chunks; i += 1) {
      await SecureStore.deleteItemAsync(
        `${LEGACY_CHUNK_PREFIX}${meta.generation}_${i}`,
      );
    }
    return draft;
  } catch {
    return null;
  }
}

export function saveReadingDraft(draft: ReadingDraft): Promise<void> {
  return serialized(async () => {
    const previous = await readMeta();
    const sameSession = previous?.sessionKey === draft.sessionKey;
    const alreadyStored = sameSession ? previous.itemCount : 0;
    if (draft.items.length < alreadyStored) {
      throw new Error("reading_draft_not_append_only");
    }
    for (let i = alreadyStored; i < draft.items.length; i += 1) {
      await writeItem(draft.sessionKey, draft.items[i]);
    }

    await commitDraftHeader(draft, previous, sameSession);
  });
}

// Correções e remoções são raras e explícitas. Regravar os itens atuais antes
// de trocar o header evita que o fluxo normal de autosave perca sua otimização.
export function mutateReadingDraft(draft: ReadingDraft): Promise<void> {
  return serialized(async () => {
    const previous = await readMeta();
    const sameSession = previous?.sessionKey === draft.sessionKey;
    for (const item of draft.items) {
      await writeItem(draft.sessionKey, item);
    }
    await commitDraftHeader(draft, previous, sameSession);
    if (previous && sameSession && previous.itemCount > draft.items.length) {
      for (let seq = draft.items.length + 1; seq <= previous.itemCount; seq += 1) {
        await deleteItem(draft.sessionKey, seq);
      }
    }
  });
}

async function commitDraftHeader(
  draft: ReadingDraft,
  previous: DraftMeta | null,
  sameSession: boolean,
): Promise<void> {
    const { items: _items, ...header } = draft;
    const stored: StoredDraft = { ...header, itemCount: draft.items.length };
    const chunks = splitSecureChunks(JSON.stringify(stored));
    const generation = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    // Chunks novos primeiro; trocar o ponteiro META e o unico commit visivel.
    for (let i = 0; i < chunks.length; i += 1) {
      await SecureStore.setItemAsync(chunkKey(generation, i), chunks[i]);
    }
    await SecureStore.setItemAsync(
      META_KEY,
      JSON.stringify({
        generation,
        chunks: chunks.length,
        sessionKey: draft.sessionKey,
        itemCount: draft.items.length,
      }),
    );

    if (previous) {
      for (let i = 0; i < previous.chunks; i += 1) {
        await SecureStore.deleteItemAsync(
          chunkKey(previous.generation, i),
        );
      }
      if (!sameSession) {
        for (let seq = 1; seq <= previous.itemCount; seq += 1) {
          await deleteItem(previous.sessionKey, seq);
        }
      }
    }
}

export function clearReadingDraft(): Promise<void> {
  return serialized(async () => {
    const meta = await readMeta();
    // Apagar o ponteiro e o commit da operacao. Falhas limpando chunks orfaos
    // nao podem fazer uma sessao descartada continuar visivel na interface.
    await SecureStore.deleteItemAsync(META_KEY);
    if (!meta) return;
    for (let i = 0; i < meta.chunks; i += 1) {
      await SecureStore.deleteItemAsync(chunkKey(meta.generation, i)).catch(() => {});
    }
    for (let seq = 1; seq <= meta.itemCount; seq += 1) {
      await deleteItem(meta.sessionKey, seq).catch(() => {});
    }
  });
}
