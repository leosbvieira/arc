import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";

const KEY = "session_token";
const URL_KEY = "bff_url";

// Endereço do BFF. Resolução: override salvo em SecureStore (editável na tela de
// login) → `extra.bffUrl` do app.json → default abaixo. NÃO use "localhost" (no
// celular é o próprio telefone); o celular precisa estar na MESMA rede (mesmo
// roteador 192.168.0.x) que o PC. Trocou de rede/DHCP? Ajuste na tela de login.
const DEFAULT_BFF_URL = "http://192.168.0.5:8000";

let cachedUrl: string | null = null;

export async function getBffUrl(): Promise<string> {
  if (cachedUrl) return cachedUrl;
  const stored = await SecureStore.getItemAsync(URL_KEY);
  cachedUrl =
    stored ||
    (Constants.expoConfig?.extra as { bffUrl?: string } | undefined)?.bffUrl ||
    DEFAULT_BFF_URL;
  return cachedUrl;
}

export async function setBffUrl(url: string): Promise<void> {
  cachedUrl = url.trim().replace(/\/+$/, "");
  await SecureStore.setItemAsync(URL_KEY, cachedUrl);
}

export async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync(KEY);
}

export async function setToken(t: string): Promise<void> {
  await SecureStore.setItemAsync(KEY, t);
}

export async function clearToken(): Promise<void> {
  await SecureStore.deleteItemAsync(KEY);
}

export async function login(password: string): Promise<string> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!r.ok) throw new Error("senha incorreta");
  const data = (await r.json()) as { token: string };
  await setToken(data.token);
  return data.token;
}

// /capture é fire-and-forget (B6): enfileira e devolve "✅ anotado". NÃO retorna a
// resposta do Hermes — para conversa síncrona (Chat) use chatSend.
export async function capture(
  text: string,
  profile?: string,
  clientKey?: string,
): Promise<string> {
  const base = await getBffUrl();
  const token = await getToken();
  const r = await fetch(`${base}/capture`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ text, profile, client_key: clientKey }),
  });
  if (!r.ok) throw new Error(`erro ${r.status}`);
  const data = (await r.json()) as { reply: string };
  return data.reply;
}

export async function logSession(body: {
  tipo: string;
  livro?: string | null;
  projeto?: string | null;
  paginas?: number | null;
  duracao_s: number;
  notas: string;
  session_key?: string | null;
}): Promise<{ ok: boolean }> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/sessions`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`erro ${r.status}`);
  return (await r.json()) as { ok: boolean };
}

// Chat síncrono: fala com o Hermes no modo escolhido (Mentor/Conselho/Capturas) e
// devolve a resposta. Rota separada do /capture (que virou fila fire-and-forget).
export async function chatSend(text: string, mode: string): Promise<string> {
  const base = await getBffUrl();
  const token = await getToken();
  const r = await fetch(`${base}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ text, mode }),
  });
  if (!r.ok) throw new Error(`erro ${r.status}`);
  const data = (await r.json()) as { reply: string };
  return data.reply;
}

export async function registerDevice(expoToken: string): Promise<void> {
  const base = await getBffUrl();
  const token = await getToken();
  await fetch(`${base}/devices`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ token: expoToken }),
  });
}

// ---- Tarefas (L1) ----
export type Task = {
  id: string;
  name: string;
  area: string;
  status: string;
  due?: string | null;
  last_done?: string | null;
  assignee?: string | null;
  severity?: "no_prazo" | "leve" | "firme" | "urgente";
  days_overdue?: number | null;
};

export type TasksByArea = { areas: { area: string; tasks: Task[] }[] };

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getToken();
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

export async function listTasks(): Promise<TasksByArea> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/tasks`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`erro ${r.status}`);
  return (await r.json()) as TasksByArea;
}

export async function createTask(name: string, area: string): Promise<void> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/tasks`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ name, area }),
  });
  if (!r.ok) throw new Error(`erro ${r.status}`);
}

export async function completeTask(id: string): Promise<void> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/tasks/${id}/complete`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!r.ok) throw new Error(`erro ${r.status}`);
}

// ---- Digest / Revisão (T-A7) ----
export type Digest = { count: number; text?: string; body: string; tasks: Task[] };

export async function getDigest(): Promise<Digest> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/digest`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`erro ${r.status}`);
  return (await r.json()) as Digest;
}

// ---- Detalhe de tarefa (com descrição, tipo ClickUp) ----
export type TaskDetail = Task & {
  priority?: string | null;
  description?: string;
  url?: string | null;
};

export async function getTaskDetail(id: string): Promise<TaskDetail> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/tasks/${id}`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`erro ${r.status}`);
  return (await r.json()) as TaskDetail;
}

// ---- Fechamento noturno (A3) ----
export type CheckItem = { rotina: string; feito: boolean };

export async function closingRoutines(template: string): Promise<string[]> {
  const base = await getBffUrl();
  const r = await fetch(
    `${base}/closing/routines?template=${encodeURIComponent(template)}`,
    { headers: await authHeaders() },
  );
  if (!r.ok) throw new Error(`routines: ${r.status}`);
  return (await r.json()).routines;
}

export async function closingDraft(
  text: string,
  template: string,
): Promise<string> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/closing/draft`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ text, template }),
  });
  if (!r.ok) throw new Error(`draft: ${r.status}`);
  return (await r.json()).draft;
}

export async function closingApprove(body: {
  raw_text: string;
  draft_md: string;
  template: string;
  checks: CheckItem[];
}): Promise<{ ok: boolean; daily_path: string }> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/closing/approve`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`approve: ${r.status}`);
  return r.json();
}
