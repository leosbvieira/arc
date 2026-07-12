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

// ---- Rotinas (P2-2) ----
// Rotinas deixaram de ser 6 checks hardcoded no BFF: agora são editáveis pelo Leo
// (CRUD na tela Rotinas). `slug` é a chave estável — é ele que vai nos checks do
// fechamento. `passos` é só roteiro (ordem dos produtos do skincare, etc.): NÃO
// conta no scorecard, quem conta é o item pai, binário.
export type Bloco = "manha" | "dia" | "noite";

export type Rotina = {
  id: number;
  slug: string;
  nome: string;
  bloco: Bloco;
  dias: string; // "*" (todo dia) | csv "seg,ter,qua,qui,sex,sab,dom"
  templates: string; // "*" (ambos) | csv "yoga,corrida"
  passos: string[]; // ORDENADO; pode ser []
  ordem: number;
  origem: "exemplo" | "leo";
};

export type RotinaInput = {
  nome: string;
  bloco: Bloco;
  dias?: string;
  templates?: string;
  passos?: string[];
};

export async function listRoutines(): Promise<Rotina[]> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/routines`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`routines: ${r.status}`);
  return ((await r.json()) as { routines: Rotina[] }).routines;
}

export async function createRoutine(body: RotinaInput): Promise<Rotina> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/routines`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`routines: ${r.status}`);
  return (await r.json()) as Rotina;
}

export async function updateRoutine(
  id: number,
  patch: Partial<RotinaInput & { ordem: number }>,
): Promise<Rotina> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/routines/${id}`, {
    method: "PATCH",
    headers: await authHeaders(),
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`routines: ${r.status}`);
  return (await r.json()) as Rotina;
}

export async function deleteRoutine(id: number): Promise<void> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/routines/${id}`, {
    method: "DELETE",
    headers: await authHeaders(),
  });
  if (!r.ok) throw new Error(`routines: ${r.status}`);
}

export async function reorderRoutines(
  ordem: { id: number; ordem: number }[],
): Promise<void> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/routines/reorder`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ ordem }),
  });
  if (!r.ok) throw new Error(`routines: ${r.status}`);
}

// ---- Pontos / Conquistas N1-4 (P2-3) ----
// Regra travada pelo Leo: fazer ganha ponto, furar desconta pouco — e só quando
// vira PADRÃO (>=3 furos da mesma rotina em 7d), nunca por furo isolado, com teto
// semanal. `nivel` é VITALÍCIO (deriva do pico, não do saldo: não regride).
// `desconto` vem positivo — é o quanto foi descontado. `delta` de padrão vem negativo.
export type PadraoSemana = {
  slug: string;
  nome: string;
  furos: number;
  delta: number; // negativo
};

export type Pontos = {
  nivel: number; // 0..4 (0 = ainda não atingiu N1)
  saldo_total: number;
  pico_total: number;
  ciclo: { indice: number; semana: number; de: number; pontos: number; meta: number };
  semana: {
    ganho: number;
    desconto: number; // positivo
    saldo: number;
    padroes: PadraoSemana[];
  };
  proximo_nivel: { n: number; faltam: number } | null; // null = já está em N4
};

export async function getPontos(): Promise<Pontos> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/pontos`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`pontos: ${r.status}`);
  return (await r.json()) as Pontos;
}

// ---- Fechamento noturno (A3) ----
export type CheckItem = { rotina: string; feito: boolean };

// Rotinas que valem HOJE — o BFF já filtra por dia da semana + template. Não
// filtre de novo no app. Vêm como objetos (antes era string[]).
export type ClosingRotina = {
  id: number;
  slug: string;
  nome: string;
  bloco: Bloco;
  passos: string[];
};

export async function closingRoutines(template: string): Promise<ClosingRotina[]> {
  const base = await getBffUrl();
  const r = await fetch(
    `${base}/closing/routines?template=${encodeURIComponent(template)}`,
    { headers: await authHeaders() },
  );
  if (!r.ok) throw new Error(`routines: ${r.status}`);
  return ((await r.json()) as { routines: ClosingRotina[] }).routines;
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

// ---- Abertura do dia (P2-5) ----
// O toque das 5h30 (template do dia) é DE MANHÃ, não às 21h. As rotinas da manhã
// também: `checkRoutine` marca UMA rotina a qualquer hora — o fechamento noturno
// respeita o que já foi marcado, não zera.
export type Template = "yoga" | "corrida";
export type Nivel = "baixa" | "media" | "alta";

export type RotinaDoDia = {
  id: number;
  slug: string;
  nome: string;
  passos: string[];
  feito: boolean;
};

export type Horario = { hora: string; ref: string };

export type Checkin = {
  feito: boolean;
  energia: string | null;
  clareza: string | null;
  prioridade_1: string | null;
};

export type Abertura = {
  data: string;
  template: Template | null; // null = ainda não respondeu o toque das 5h30
  rotinas_manha: RotinaDoDia[];
  prioridades_de_ontem: string[]; // vêm do Shutdown de ontem; [] se não houve
  hoje: { tarefas_due: Task[]; horarios: Horario[] };
  checkin: Checkin;
};

export async function getAbertura(): Promise<Abertura> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/abertura`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`abertura: ${r.status}`);
  return (await r.json()) as Abertura;
}

export async function setTemplateDia(template: Template): Promise<void> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/dia/template`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ template }),
  });
  if (!r.ok) throw new Error(`template: ${r.status}`);
}

export async function checkRoutine(slug: string, feito: boolean): Promise<void> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/routines/check`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ slug, feito }),
  });
  if (!r.ok) throw new Error(`check: ${r.status}`);
}

export async function postCheckin(body: {
  energia: Nivel;
  clareza: Nivel;
  prioridade_1: string;
}): Promise<void> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/abertura/checkin`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`checkin: ${r.status}`);
}

// ---- Shutdown das 19h (P2-6) ----
// Rito de ENCERRAR O TRABALHO — não confundir com o fechamento noturno das 21h
// (diário + rotinas). O entregável daqui são as 3 prioridades de amanhã, que
// reaparecem na Abertura de amanhã como `prioridades_de_ontem`.
export type Shutdown = {
  data: string;
  trabalho_aberto: Task[];
  follow_ups: Task[];
  // mais_velho_d vem null quando o staging está vazio (n === 0).
  staging: { n: number; mais_velho_d: number | null };
  prioridades: string[];
  feito: boolean;
};

export async function getShutdown(): Promise<Shutdown> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/shutdown`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`shutdown: ${r.status}`);
  return (await r.json()) as Shutdown;
}

export async function postShutdown(prioridades: string[]): Promise<void> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/shutdown`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ prioridades: prioridades.slice(0, 3) }),
  });
  if (!r.ok) throw new Error(`shutdown: ${r.status}`);
}
