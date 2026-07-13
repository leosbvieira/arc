import { getBffUrl, getToken } from "./api";

export type ReadingHook =
  | "quote"
  | "comentario"
  | "ideia"
  | "coach"
  | "lista"
  | "texto";

export type ReadingBufferChunk = {
  seq: number;
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
  fim: number | null;
  status: "pending" | "compiling" | "compiled" | "discarded";
  buffer?: ReadingBufferChunk[];
  texto?: string;
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
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: await headers(),
  });
  if (!response.ok) throw new Error(`reading: ${response.status}`);
  return (await response.json()) as T;
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

export async function listPendingReadingSessions(): Promise<{
  sessions: ReadingSession[];
}> {
  return request("/reading/sessions/pending");
}

export async function compileReadingSession(
  sessionId: number,
  body: { pagina_final: number | null; fim: number },
): Promise<{ session: ReadingSession; anki_cards: unknown[] }> {
  return request(`/reading/sessions/${sessionId}/compile`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function discardReadingSession(
  sessionId: number,
): Promise<{ session: ReadingSession }> {
  return request(`/reading/sessions/${sessionId}/discard`, {
    method: "POST",
  });
}
