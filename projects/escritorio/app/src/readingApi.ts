import { getBffUrl, getToken } from "./api";
import { ReadingApiError } from "./readingApiError";

export { ReadingApiError, readingErrorDetail } from "./readingApiError";

export type ReadingHook =
  | "quote"
  | "comentario"
  | "ideia"
  | "coach"
  | "lista"
  | "texto";

export type ReadingBufferChunk = {
  seq: number;
  chunk_id: string;
  hook: ReadingHook;
  texto: string;
  ts: number;
};

export type ReadingSession = {
  id: number;
  client_key: string;
  livro: string;
  pagina_inicial: number | null;
  pagina_final: number | null;
  inicio: number;
  updated: number;
  fim: number | null;
  status: "pending" | "compiling" | "compiled" | "discarded";
  last_seq?: number;
  vault_path?: string | null;
  compiled_session_id?: number | null;
  source_digest?: string | null;
  // Presente quando a sessão está "staged": nota gerada pelo Hermes, ainda fora
  // do vault (status segue "pending", buffer congelado). Aprovar grava; rejeitar limpa.
  draft_md?: string | null;
  buffer?: ReadingBufferChunk[];
  texto?: string;
};

export type ReadingSnapshot = {
  client_key: string;
  livro: string;
  pagina_inicial: number | null;
  pagina_final: number | null;
  buffer: Array<Pick<ReadingBufferChunk, "seq" | "hook" | "texto">>;
};

export type ReadingReconcileResult = {
  state: "pending" | "compiled";
  matched: boolean;
  session: ReadingSession;
  anki_cards: unknown[];
};

async function headers(): Promise<Record<string, string>> {
  const token = await getToken();
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const base = await getBffUrl();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch(`${base}${path}`, {
      ...init,
      headers: await headers(),
      signal: controller.signal,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null) as { detail?: string } | null;
      throw new ReadingApiError(
        response.status,
        payload?.detail ?? "reading_indisponivel",
      );
    }
    return (await response.json()) as T;
  } catch (error) {
    if (controller.signal.aborted) {
      throw new ReadingApiError(0, "reading_timeout");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function createReadingSession(body: {
  client_key: string;
  livro: string;
  pagina_inicial: number | null;
  inicio: number;
}): Promise<{ session: ReadingSession; created: boolean }> {
  return request("/reading/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function appendReadingBuffer(
  sessionId: number,
  body: {
    seq: number;
    hook: ReadingHook;
    texto: string;
    ts: number;
  },
): Promise<{ chunk: ReadingBufferChunk; created: boolean }> {
  return request(`/reading/sessions/${sessionId}/buffer`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateLastReadingBuffer(
  sessionId: number,
  seq: number,
  body: { expected_chunk_id: string; hook: ReadingHook; texto: string },
): Promise<{ chunk: ReadingBufferChunk; updated: boolean }> {
  return request(`/reading/sessions/${sessionId}/buffer/${seq}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteLastReadingBuffer(
  sessionId: number,
  seq: number,
  expectedChunkId: string,
): Promise<{ deleted: boolean; session: ReadingSession }> {
  return request(`/reading/sessions/${sessionId}/buffer/${seq}?expected_chunk_id=${encodeURIComponent(expectedChunkId)}`, {
    method: "DELETE",
  });
}

export async function listPendingReadingSessions(): Promise<{
  sessions: ReadingSession[];
}> {
  return request("/reading/sessions/pending");
}

export async function getReadingSession(
  sessionId: number,
): Promise<{ session: ReadingSession }> {
  return request(`/reading/sessions/${sessionId}`);
}

export async function reconcileReadingSession(
  sessionId: number,
  snapshot: ReadingSnapshot,
): Promise<ReadingReconcileResult> {
  return request(`/reading/sessions/${sessionId}/reconcile`, {
    method: "POST",
    body: JSON.stringify(snapshot),
  });
}

// Gera o preview da nota (Hermes) e o guarda como draft_md — SEM gravar no vault.
// A sessão segue "pending" e o buffer fica congelado no servidor. É o "Compilar".
export async function draftReadingSession(
  sessionId: number,
  body: { pagina_final: number | null },
): Promise<{ session: ReadingSession; draft_md: string }> {
  return request(`/reading/sessions/${sessionId}/draft`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// Aprova o rascunho: grava no vault + Anki + purga o buffer. Exige um draft_md
// (o BFF devolve 422 reading_draft_ausente se não houver preview gerado antes).
export async function compileReadingSession(
  sessionId: number,
  body: { pagina_final: number | null; fim: number; duracao_s: number },
): Promise<{
  session: ReadingSession;
  anki_cards: unknown[];
  anki_status: "pending" | "done";
}> {
  return request(`/reading/sessions/${sessionId}/compile`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// Rejeita o rascunho: limpa draft_md e devolve o buffer à edição (status "pending").
export async function rejectReadingDraft(
  sessionId: number,
): Promise<{ session: ReadingSession }> {
  return request(`/reading/sessions/${sessionId}/draft`, {
    method: "DELETE",
  });
}

export async function discardReadingSession(
  sessionId: number,
): Promise<{ session: ReadingSession }> {
  return request(`/reading/sessions/${sessionId}/discard`, {
    method: "POST",
  });
}
