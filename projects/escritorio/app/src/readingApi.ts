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

export type Book = {
  id: number;
  titulo: string;
  // "terminando" = reservada enquanto o resumão é criado no ClickUp. Terminar tem
  // efeito externo, e o POST do ClickUp não é idempotente: a obra fica nesse estado
  // até se provar o que aconteceu lá fora, e é por isso que ele existe na tela.
  status: "lendo" | "terminando" | "terminado";
  ciclo: number;
  // Derivadas do servidor: null = a obra ainda não tem sessão compilada no ciclo.
  pagina_atual: number | null;
  ultima_sessao: number | null; // segundos, como o servidor manda
  sessoes_n: number;
  // Só vem preenchido quando o resumão é DESTE ciclo: reabrir incrementa o ciclo e
  // a tarefa da leitura anterior deixa de valer para a atual.
  resumo_task_id?: string | null;
  terminando_desde?: number | null;
};

export type ReadingSession = {
  id: number;
  client_key: string;
  livro: string;
  book_id: number | null;
  book_ciclo: number | null;
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

// Autosave, criar sessão, estante: rede e SQLite, nada mais. 12s já é folgado, e
// esperar mais só atrasaria o aviso de que o BFF caiu.
const TIMEOUT_MS = 12_000;

// Compor e publicar a nota passam pelo Hermes, que o BFF espera por 150s. Com 12s o
// celular desistia no meio e dizia "não foi possível gerar o preview" enquanto o
// servidor terminava o serviço e gravava o rascunho — a mensagem mentia sobre um
// trabalho que deu certo, e o custo era ele apagar e reditar o que já existia.
// A margem sobre os 150s é para a resposta voltar, não para esperar mais Hermes.
const TIMEOUT_HERMES_MS = 165_000;

async function request<T>(
  path: string,
  init?: RequestInit,
  timeoutMs: number = TIMEOUT_MS,
): Promise<T> {
  const base = await getBffUrl();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
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
  book_id?: number | null;
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
  return request(
    `/reading/sessions/${sessionId}/draft`,
    { method: "POST", body: JSON.stringify(body) },
    TIMEOUT_HERMES_MS,
  );
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
  // Aprovar grava no vault e ainda pede os cards ao Hermes na mesma chamada. Desistir
  // aos 12s aqui é pior que no preview: a nota vai para o Obsidian de qualquer jeito e
  // o app fica achando que a sessão não fechou.
  return request(
    `/reading/sessions/${sessionId}/compile`,
    { method: "POST", body: JSON.stringify(body) },
    TIMEOUT_HERMES_MS,
  );
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

export async function listBooks(
  status: "lendo" | "terminando" | "terminado" = "lendo",
): Promise<{ books: Book[] }> {
  return request(`/reading/books?status=${status}`);
}

export async function createBook(
  titulo: string,
): Promise<{ book: Book; created: boolean }> {
  return request("/reading/books", {
    method: "POST",
    body: JSON.stringify({ titulo }),
  });
}

// Cria a tarefa de resumão no Staging e fecha o ciclo. `resumo_task_id` vem null
// quando o ciclo não teve sessão nenhuma — não há o que resumir.
export async function terminarBook(
  bookId: number,
): Promise<{ book: Book; resumo_task_id: string | null }> {
  // Passa pelo ClickUp, então herda a paciência do Hermes em vez dos 12s de rede.
  return request(
    `/reading/books/${bookId}/terminar`,
    { method: "POST" },
    TIMEOUT_HERMES_MS,
  );
}

// Resolve uma obra presa em "terminando" perguntando ao ClickUp se a tarefa existe.
// `resultado` diz o que foi decidido: "terminado" (achou e adotou) ou "liberado"
// (provou que não existe e devolveu a obra para a estante).
export async function reconciliarTerminarBook(bookId: number): Promise<{
  book: Book;
  resumo_task_id: string | null;
  resultado: "terminado" | "liberado";
}> {
  return request(
    `/reading/books/${bookId}/terminar/reconciliar`,
    { method: "POST" },
    TIMEOUT_HERMES_MS,
  );
}

export async function reabrirBook(bookId: number): Promise<{ book: Book }> {
  return request(`/reading/books/${bookId}/reabrir`, { method: "POST" });
}
