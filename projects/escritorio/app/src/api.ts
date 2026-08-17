import Constants from "expo-constants";
import { mensagemDaFalhaDoChat, segundosDoRetryAfter } from "./chatError";
import * as SecureStore from "./storage";

const KEY = "session_token";
const URL_KEY = "bff_url";

// Endereço do BFF. Resolução: override salvo em SecureStore (editável na tela de
// login) → `extra.bffUrl` do app.json → default abaixo. NÃO use "localhost" (no
// celular é o próprio telefone); o celular precisa estar na MESMA rede (mesmo
// roteador 192.168.0.x) que o PC. Trocou de rede/DHCP? Ajuste na tela de login.
const DEFAULT_BFF_URL = "http://192.168.0.2:8000";

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
  // "senha incorreta" para QUALQUER status era mentira em dois casos novos: o 429 do
  // limitador (insistir é exatamente o que não se deve fazer) e um 5xx do servidor.
  if (r.status === 429) {
    const s = segundosDoRetryAfter(r.headers.get("Retry-After"));
    const espera = s ? ` — espere ${Math.ceil(s / 60)} min` : "";
    throw new Error(`tentativas demais${espera}`);
  }
  if (r.status >= 500) throw new Error(`o servidor falhou (erro ${r.status})`);
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
  sensivel: boolean = false,
): Promise<string> {
  const base = await getBffUrl();
  const token = await getToken();
  const r = await fetch(`${base}/capture`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      text,
      profile,
      client_key: clientKey,
      sensivel,
    }),
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
export type ChatTurno = { role: "user" | "ai"; text: string };

// Teto do lado do cliente. O servidor tem HERMES_TIMEOUT=150s e o slot do Hermes é
// UM só, compartilhado por chat, captura, triagem, leitura, anki, diário e review —
// então uma captura em fundo pode segurar a fala do Mentor por mais de dois minutos.
// Sem AbortController isso não tinha teto NENHUM: `sending` ficava true, o campo e o
// botão travados, e como o App mantém o Chat montado, trocar de aba não resolvia.
// Matar o app resolvia — e levava a conversa junto, que só vive em `useState`.
// O valor dá folga sobre os 150s do servidor: abortar antes dele seria transformar
// resposta lenta em erro, e o `readingApi.ts` já usa a mesma folga (165s).
// A conta TEM que fechar com o servidor, e a primeira versão errou: 30s de espera
// pelo slot + 150s do Hermes = 180s, contra 175s aqui — o cliente abortaria pedido que
// ia dar certo, o exato defeito que este teto existe para evitar. Hoje o servidor cabe
// em 15 (montar) + 20 (slot) + 150 (Hermes) + 10 (margem) = 195, e um teste no BFF
// (`test_o_orcamento_do_chat_fecha`) cobra essa soma contra o número abaixo.
const TIMEOUT_CHAT_MS = 200_000;

export async function chatSend(
  text: string,
  mode: string,
  historico: ChatTurno[] = [],
): Promise<string> {
  const base = await getBffUrl();
  const token = await getToken();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_CHAT_MS);
  try {
    return await chatRequest(base, token, text, mode, historico, controller.signal);
  } catch (erro) {
    // AbortError vira frase, não código: este texto vai DIRETO pra bolha de IA na
    // conversa (o catch do Chat.tsx põe `e.message` na tela).
    if (erro instanceof Error && erro.name === "AbortError") {
      throw new Error(
        "demorei demais pra responder — sua mensagem continua aqui, tente de novo",
      );
    }
    throw erro;
  } finally {
    clearTimeout(timeout);
  }
}

async function chatRequest(
  base: string,
  token: string | null,
  text: string,
  mode: string,
  historico: ChatTurno[],
  signal: AbortSignal,
): Promise<string> {
  const r = await fetch(`${base}/chat`, {
    signal,
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ text, mode, historico }),
  });
  if (!r.ok) {
    // A mensagem desta exception vira BOLHA DE IA na tela (o `catch` de Chat.tsx põe
    // `e.message` na conversa). Por isso ela já é a frase final, e não um código:
    // "erro 502" tratava cota esgotada, PC desligado e timeout como a mesma coisa.
    const payload = (await r.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(
      mensagemDaFalhaDoChat({
        status: r.status,
        detail: payload?.detail ?? null,
        retryAposS: segundosDoRetryAfter(r.headers.get("Retry-After")),
      }),
    );
  }
  const data = (await r.json()) as { reply: string };
  return data.reply;
}

export async function registerDevice(expoToken: string): Promise<void> {
  const base = await getBffUrl();
  const token = await getToken();
  const response = await fetch(`${base}/devices`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ token: expoToken }),
  });
  if (!response.ok) throw new Error(`registrar push: ${response.status}`);
}

export async function unregisterDevice(expoToken: string): Promise<void> {
  const base = await getBffUrl();
  const token = await getToken();
  const response = await fetch(`${base}/devices`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ token: expoToken }),
  });
  if (!response.ok) throw new Error(`remover push: ${response.status}`);
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

/** `due` = YYYY-MM-DD e `hora` = HH:MM (o BFF valida fail-closed). Sem `due` a
 *  tarefa nasce sem prazo e o motor de cobrança NUNCA a seleciona; com `hora`, o
 *  BFF também agenda o ⏰. */
export async function createTask(
  name: string,
  area: string,
  due?: string | null,
  hora?: string | null,
): Promise<void> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/tasks`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({
      name,
      area,
      ...(due ? { due } : {}),
      ...(hora ? { hora } : {}),
    }),
  });
  if (!r.ok) throw new Error(`erro ${r.status}`);
}

/** Remarca o prazo (YYYY-MM-DD). Lei 4: replanejar, nao envergonhar — sem isto a
 *  unica forma de calar uma cobranca e concluir mentindo. */
export async function adiarTask(id: string, due: string): Promise<void> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/tasks/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: await authHeaders(),
    body: JSON.stringify({ due }),
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
    teto_desconto: number;
  };
  proximo_nivel: { n: number; faltam: number } | null; // null = já está em N4
};

export async function getPontos(): Promise<Pontos> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/pontos`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`pontos: ${r.status}`);
  return (await r.json()) as Pontos;
}

/** Como o SISTEMA funciona (tarifas, limiares, horários). O SEU estado é /pontos.
 *  Devolve o corpo cru: quem valida é o parametrosCore, contra o schema. */
export async function getParametros(): Promise<{ ok: boolean; corpo?: unknown; status: number | null }> {
  try {
    const base = await getBffUrl();
    const r = await fetch(`${base}/wiki/parametros`, { headers: await authHeaders() });
    if (!r.ok) return { ok: false, status: r.status };
    return { ok: true, corpo: await r.json(), status: r.status };
  } catch {
    return { ok: false, status: null };
  }
}

// ---- Hábitos a reduzir ----------------------------------------------------
export type ReductionHabit = {
  id: number;
  slug: string;
  nome: string;
  penalidade: number;
  criado: number;
  atualizado: number;
};

export type ReductionOccurrence = {
  id: number;
  habito_id: number;
  data: string;
  registrada_em: number;
  client_key: string | null;
  penalidade: number;
  desfeita_em: number | null;
  slug: string;
  nome: string;
  penalizavel: boolean;
  desfeita: boolean;
};

export async function listReductionHabits(): Promise<ReductionHabit[]> {
  const base = await getBffUrl();
  const response = await fetch(`${base}/habitos-reduzir`, { headers: await authHeaders() });
  if (!response.ok) throw new Error(`hábitos: ${response.status}`);
  return ((await response.json()) as { habitos: ReductionHabit[] }).habitos;
}

export async function createReductionHabit(nome: string, penalidade: number): Promise<ReductionHabit> {
  const base = await getBffUrl();
  const response = await fetch(`${base}/habitos-reduzir`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ nome, penalidade }),
  });
  if (!response.ok) throw new Error(`criar hábito: ${response.status}`);
  return (await response.json()) as ReductionHabit;
}

export async function deleteReductionHabit(id: number): Promise<void> {
  const base = await getBffUrl();
  const response = await fetch(`${base}/habitos-reduzir/${id}`, {
    method: "DELETE",
    headers: await authHeaders(),
  });
  if (!response.ok) throw new Error(`arquivar hábito: ${response.status}`);
}

export async function listReductionOccurrences(): Promise<ReductionOccurrence[]> {
  const base = await getBffUrl();
  const response = await fetch(`${base}/habitos-reduzir/historico`, { headers: await authHeaders() });
  if (!response.ok) throw new Error(`histórico de hábitos: ${response.status}`);
  return ((await response.json()) as { ocorrencias: ReductionOccurrence[] }).ocorrencias;
}

export async function recordReductionOccurrence(
  habitId: number,
  clientKey: string,
  data: string,
): Promise<ReductionOccurrence> {
  const base = await getBffUrl();
  const response = await fetch(`${base}/habitos-reduzir/${habitId}/ocorrencias`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ client_key: clientKey, data }),
  });
  if (!response.ok) throw new Error(`registrar ocorrência: ${response.status}`);
  return ((await response.json()) as { ocorrencia: ReductionOccurrence }).ocorrencia;
}

export async function undoReductionOccurrence(id: number): Promise<ReductionOccurrence> {
  const base = await getBffUrl();
  const response = await fetch(`${base}/habitos-reduzir/ocorrencias/${id}/undo`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!response.ok) throw new Error(`desfazer ocorrência: ${response.status}`);
  return ((await response.json()) as { ocorrencia: ReductionOccurrence }).ocorrencia;
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
  /** Estado do dia vindo do servidor: sem ele a tela das 21h apagaria a manhã. */
  feito: boolean;
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

export type EventoAgenda = {
  hora: string | null;
  titulo: string;
  fonte: "gcal" | "outlook" | "hora_marcada" | string;
  inicio_ts?: number | null;
};

export type EstadoFonteCalendario = "ok" | "cache" | "erro" | "nao_configurado";

export type TemaSemana = {
  id: number;
  semana: string;
  texto: string;
  criado: number;
};

export type Checkin = {
  feito: boolean;
  energia: string | null;
  clareza: string | null;
  prioridade_1: string | null;
};

export type Abertura = {
  data: string;
  /** Dias desde a última interação. >=7 dispara o Modo Retorno na Home (lei 4). */
  dias_ausente?: number;
  template: Template | null; // null = ainda não respondeu o toque das 5h30
  rotinas_manha: RotinaDoDia[];
  /** O dia INTEIRO (manhã + tarde + noite). A Home conta por aqui. */
  rotinas_hoje?: { feitas: number; total: number };
  prioridades_de_ontem: string[]; // vêm do Shutdown de ontem; [] se não houve
  temas: TemaSemana[];
  hoje: {
    tarefas_due: Task[];
    /** true = a fonte externa não respondeu. Lista vazia NÃO quer dizer "sem tarefa":
     *  sem este campo, falha e calma viram a mesma tela. */
    tarefas_indisponivel?: boolean;
    horarios: Horario[];
    calendario: EventoAgenda[];
    fontes_calendario: Record<string, EstadoFonteCalendario>;
  };
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
    // Sem `.slice(0, 3)`: era a QUARTA cópia do número. A tela desenha exatamente
    // as caixas que o servidor manda, e o servidor valida contra a mesma constante.
    body: JSON.stringify({ prioridades }),
  });
  if (!r.ok) throw new Error(`shutdown: ${r.status}`);
}

// ---- Agenda e temas da semana (P2-7/8) ----
export type Agenda = {
  data: string;
  eventos: EventoAgenda[];
  temas: TemaSemana[];
  fontes: Record<string, EstadoFonteCalendario>;
  tarefas_due: Task[];
};

export async function getAgenda(data?: string): Promise<Agenda> {
  const base = await getBffUrl();
  const query = data ? `?data=${encodeURIComponent(data)}` : "";
  const r = await fetch(`${base}/agenda${query}`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`agenda: ${r.status}`);
  return (await r.json()) as Agenda;
}

export type GoogleCalendarEventInput = {
  titulo: string;
  data: string;
  hora: string;
  duracao_min: number;
  client_key: string;
};

export type GoogleCalendarEvent = {
  id: string;
  titulo: string;
  html_link: string | null;
  inicio: string;
  fim: string;
  fonte: "gcal";
};

export async function createGoogleCalendarEvent(
  body: GoogleCalendarEventInput,
): Promise<GoogleCalendarEvent> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/agenda/google-calendar`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const payload = (await r.json().catch(() => null)) as { detail?: string } | null;
    if (r.status === 503 && payload?.detail === "google_calendar_nao_configurado") {
      const error = new Error("Google Calendar não configurado no servidor.");
      error.name = "GoogleCalendarNotConfigured";
      throw error;
    }
    if (r.status === 503) throw new Error("Google Calendar indisponível agora.");
    if (r.status === 409) throw new Error("Este envio mudou; revise e confirme de novo.");
    const error = new Error(`Google Calendar: ${r.status}`);
    error.name = `GoogleCalendarHttp${r.status}`;
    throw error;
  }
  return ((await r.json()) as { evento: GoogleCalendarEvent }).evento;
}

export async function listTemas(semana?: string): Promise<{ semana: string; temas: TemaSemana[] }> {
  const base = await getBffUrl();
  const query = semana ? `?semana=${encodeURIComponent(semana)}` : "";
  const r = await fetch(`${base}/temas${query}`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`temas: ${r.status}`);
  return (await r.json()) as { semana: string; temas: TemaSemana[] };
}

export async function addTema(texto: string, semana?: string): Promise<TemaSemana> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/temas`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ texto, semana }),
  });
  if (!r.ok) throw new Error(`temas: ${r.status}`);
  return (await r.json()) as TemaSemana;
}

export async function deleteTema(id: number): Promise<void> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/temas/${id}`, {
    method: "DELETE",
    headers: await authHeaders(),
  });
  if (!r.ok) throw new Error(`temas: ${r.status}`);
}

// ---- Review semanal/mensal e objetivos acumulativos (P2-9) ----
export type ScorecardReview = {
  pct: number;
  por_rotina: Record<string, { feitos: number; dias: number }>;
};

export type ReviewWeekly = {
  week: string;
  desde: string;
  scorecard: ScorecardReview;
  objetivos: { nome: string; n_semana: number; alvo: number | null; pct: number | null }[];
  edificacao: { novos: number; pratica: Aprendizado | null };
  /** Opcional de propósito: um APK novo pode falar com um BFF antigo, e a tela
   *  não pode quebrar por causa de um campo que ainda não existe do outro lado.
   *
   *  `escolhiveis` e `a_triar` são separados porque o CTA precisa prometer a ação
   *  que a tela de destino realmente oferece: o card de "a triar" só tem os chips
   *  de alvo, o botão "fazer esta semana" mora no card da fila. */
  melhorias?: {
    paradas: number;
    a_triar: number;
    escolhiveis: number;
    escolhida: Melhoria | null;
    vencidas: Melhoria[];
    app: number;
  };
  dailies: number;
  capturas: number;
  sessoes_leitura: { n: number; min_total: number };
  tarefas_concluidas: number | null;
  staging_pendentes: number | null;
};

export type ReviewMonthly = {
  mes: string;
  scorecard: ScorecardReview;
  dailies: number;
  capturas: number;
  sessoes_leitura: { n: number; min_total: number };
  pontos: { ganho: number; desconto: number; saldo: number };
  objetivos: { nome: string; total_no_mes: number }[];
  patrimonio: string;
  tarefas_concluidas?: number | null;
  staging_pendentes?: number | null;
};

export async function getReviewWeekly(): Promise<ReviewWeekly> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/review/weekly`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`review semanal: ${r.status}`);
  return (await r.json()) as ReviewWeekly;
}

/** Fecha o review da semana: grava o artefato no vault e registra que aconteceu.
 *  Sem esse registro, "2 semanas puladas -> Mentor" e impossivel de responder. */
export async function approveWeeklyReview(
  semana?: string,
): Promise<{ ok: boolean; semana: string; vault_path: string }> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/review/weekly/approve`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify(semana ? { semana } : {}),
  });
  if (!r.ok) throw new Error(`erro ${r.status}`);
  return (await r.json()) as { ok: boolean; semana: string; vault_path: string };
}

export async function getReviewMonthly(): Promise<ReviewMonthly> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/review/monthly`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`review mensal: ${r.status}`);
  return (await r.json()) as ReviewMonthly;
}

export type Objetivo = {
  id: number;
  nome: string;
  rotina_slug: string | null;
  alvo_semana: number | null;
  criado: number;
  ativo: number | boolean;
  progresso: {
    total: number;
    semana_atual: { n: number; alvo: number | null; pct: number | null };
    serie: { semana: string; n: number }[];
  };
};

export async function listObjetivos(): Promise<Objetivo[]> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/objetivos`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`objetivos: ${r.status}`);
  return ((await r.json()) as { objetivos: Objetivo[] }).objetivos;
}

export async function createObjetivo(body: {
  nome: string;
  rotina_slug?: string | null;
  alvo_semana?: number | null;
}): Promise<Objetivo> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/objetivos`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`objetivos: ${r.status}`);
  return ((await r.json()) as { objetivo: Objetivo }).objetivo;
}

export async function updateObjetivo(
  id: number,
  patch: { nome?: string; alvo_semana?: number | null },
): Promise<Objetivo> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/objetivos/${id}`, {
    method: "PATCH",
    headers: await authHeaders(),
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`objetivos: ${r.status}`);
  return ((await r.json()) as { objetivo: Objetivo }).objetivo;
}

export async function deleteObjetivo(id: number): Promise<void> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/objetivos/${id}`, {
    method: "DELETE",
    headers: await authHeaders(),
  });
  if (!r.ok) throw new Error(`objetivos: ${r.status}`);
}

export async function setObjetivoHoje(id: number, marcado: boolean): Promise<void> {
  const base = await getBffUrl();
  const acao = marcado ? "marcar" : "desmarcar";
  const r = await fetch(`${base}/objetivos/${id}/${acao}`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({}),
  });
  if (!r.ok) throw new Error(`objetivos: ${r.status}`);
}

// ---- Edificacao minima (P2-10) ----
export type AprendizadoStatus = "novo" | "pratica" | "aplicado" | "arquivado";

export type Aprendizado = {
  id: number;
  texto: string;
  sensivel: number | boolean;
  origem_captura_id: number | null;
  status: AprendizadoStatus;
  pratica_semana: string | null;
  pratica_em: number | null;
  criado: number;
};

export async function listAprendizados(status?: AprendizadoStatus): Promise<Aprendizado[]> {
  const base = await getBffUrl();
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const r = await fetch(`${base}/aprendizados${query}`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`aprendizados: ${r.status}`);
  return ((await r.json()) as { aprendizados: Aprendizado[] }).aprendizados;
}

export async function createAprendizado(texto: string, sensivel: boolean): Promise<Aprendizado> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/aprendizados`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ texto, sensivel }),
  });
  if (!r.ok) throw new Error(`aprendizados: ${r.status}`);
  return (await r.json()) as Aprendizado;
}

export async function praticarAprendizado(id: number): Promise<Aprendizado> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/aprendizados/${id}/praticar`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!r.ok) throw new Error(`aprendizados: ${r.status}`);
  return (await r.json()) as Aprendizado;
}

export async function setAprendizadoStatus(
  id: number,
  status: Exclude<AprendizadoStatus, "pratica">,
): Promise<Aprendizado> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/aprendizados/${id}/status`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ status }),
  });
  if (!r.ok) throw new Error(`aprendizados: ${r.status}`);
  return (await r.json()) as Aprendizado;
}

// ---- Melhorias (fila sem prazo: app / empresa / fluxo) ----
//
// Não é tarefa e não vai pro ClickUp de propósito: melhoria não tem prazo, tem
// momento. Nas áreas da triagem não existe nenhuma que seja "o sistema", e sem
// prazo ela cairia no bucket `backlog` da tela Tasks — o cemitério.
// O vocabulário de alvo mora em `melhoriasView.ts` (módulo puro, testável fora
// do react-native) e é reexportado aqui para quem só conhece a camada de API.
export { ALVOS_MELHORIA } from "./melhoriasView";
export type { AlvoMelhoria } from "./melhoriasView";

import type { AlvoMelhoria } from "./melhoriasView";

export type MelhoriaStatus = "novo" | "escolhida" | "feita" | "descartada";

export type Melhoria = {
  id: number;
  texto: string;
  alvo: AlvoMelhoria | null;
  sensivel: number | boolean;
  origem_captura_id: number | null;
  status: MelhoriaStatus;
  escolhida_semana: string | null;
  escolhida_em: number | null;
  criado: number;
};

/** A `semana` vem junto para a tela saber se a escolhida é DESTA semana sem
 *  recalcular data no cliente. Um BFF antigo não manda o campo — daí o `?? null`,
 *  que faz a tela mostrar a semana do próprio item em vez de chutar. */
export async function listMelhorias(
  alvo?: AlvoMelhoria,
): Promise<{ melhorias: Melhoria[]; semana: string | null }> {
  const base = await getBffUrl();
  const query = alvo ? `?alvo=${encodeURIComponent(alvo)}` : "";
  const r = await fetch(`${base}/melhorias${query}`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`melhorias: ${r.status}`);
  const corpo = (await r.json()) as { melhorias: Melhoria[]; semana?: string };
  return { melhorias: corpo.melhorias, semana: corpo.semana ?? null };
}

export async function createMelhoria(
  texto: string,
  alvo: AlvoMelhoria | null,
  sensivel: boolean,
): Promise<Melhoria> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/melhorias`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ texto, alvo, sensivel }),
  });
  if (!r.ok) throw new Error(`melhorias: ${r.status}`);
  return (await r.json()) as Melhoria;
}

export async function setMelhoriaAlvo(id: number, alvo: AlvoMelhoria): Promise<Melhoria> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/melhorias/${id}/alvo`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ alvo }),
  });
  if (!r.ok) throw new Error(`melhorias: ${r.status}`);
  return (await r.json()) as Melhoria;
}

export async function escolherMelhoria(id: number): Promise<Melhoria> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/melhorias/${id}/escolher`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!r.ok) throw new Error(`melhorias: ${r.status}`);
  return (await r.json()) as Melhoria;
}

export async function setMelhoriaStatus(
  id: number,
  status: Exclude<MelhoriaStatus, "escolhida">,
): Promise<Melhoria> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/melhorias/${id}/status`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ status }),
  });
  if (!r.ok) throw new Error(`melhorias: ${r.status}`);
  return (await r.json()) as Melhoria;
}

// ---- Triagem em lote (P2-13) ----
export const AREAS_TRIAGEM = [
  "Trabalho", "Corpo", "Saúde Mental", "Responsabilidade", "Finance",
  "Carreira", "Estudo", "Relacionamentos", "Lazer",
] as const;

export type AreaTriagem = (typeof AREAS_TRIAGEM)[number];

export type ItemTriagem = {
  id: string;
  name: string;
  idade_d: number | null;
  area_proposta: AreaTriagem | null;
};

// O tipo mora em `triagemResultado.ts`, junto da tradução das causas — assim o módulo
// puro pode ser testado com `node --test` sem arrastar este arquivo (que tem fetch).
export type { ResultadoTriagem } from "./triagemResultado";
import type { ResultadoTriagem } from "./triagemResultado";

export async function getTriagem(): Promise<{ itens: ItemTriagem[]; n: number }> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/triagem`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`triagem: ${r.status}`);
  return (await r.json()) as { itens: ItemTriagem[]; n: number };
}

export async function aplicarTriagem(
  // `due` no formato civil YYYY-MM-DD, que é o que o BFF valida (fail-closed).
  // Ausente = sem prazo; o servidor não inventa data quando ele não pediu uma.
  movimentos: { task_id: string; area: AreaTriagem; due?: string }[],
): Promise<ResultadoTriagem[]> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/triagem/aplicar`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ movimentos }),
  });
  if (!r.ok) throw new Error(`triagem: ${r.status}`);
  return ((await r.json()) as { resultados: ResultadoTriagem[] }).resultados;
}

// Contratos do Anki ficam prontos para a Rodada J, sem acoplar a captura atual.
export type AnkiStatus = "sugerido" | "aprovado" | "descartado" | "exportado";
export type AnkiCard = {
  id: number;
  session_id: number | null;
  frente: string;
  meaning: string;
  example: string;
  hook: string;
  deck: string | null;
  status: AnkiStatus;
  criado: number;
};

export async function suggestAnki(notas: string, sessionId?: number): Promise<AnkiCard[]> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/anki/sugerir`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ notas, session_id: sessionId }),
  });
  if (!r.ok) throw new Error(`anki: ${r.status}`);
  return ((await r.json()) as { cards: AnkiCard[] }).cards;
}

export async function listAnkiCards(status?: AnkiStatus): Promise<AnkiCard[]> {
  const base = await getBffUrl();
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const r = await fetch(`${base}/anki/cards${query}`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`anki: ${r.status}`);
  return ((await r.json()) as { cards: AnkiCard[] }).cards;
}

export async function updateAnkiCard(
  id: number,
  patch: Partial<Pick<AnkiCard, "frente" | "meaning" | "example" | "hook" | "deck">> & {
    status?: Exclude<AnkiStatus, "exportado">;
  },
): Promise<AnkiCard> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/anki/cards/${id}`, {
    method: "PATCH",
    headers: await authHeaders(),
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`anki: ${r.status}`);
  return (await r.json()) as AnkiCard;
}

export async function exportAnki(): Promise<{ n: number; path: string | null; tsv: string }> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/anki/export`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!r.ok) throw new Error(`anki: ${r.status}`);
  return (await r.json()) as { n: number; path: string | null; tsv: string };
}


// --- capturas que pararam de vez ------------------------------------------
// O digest diário manda "abrir o app" quando há capturas não processadas, e até aqui
// abrir o app não adiantava: nenhuma tela conhecia estas duas rotas. O conteúdo é
// coisa que o Leo ditou e acredita estar arquivada — o /capture responde na hora.

export async function contarCapturasFalhadas(): Promise<number> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/captures/failed`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`erro ${r.status}`);
  return ((await r.json()) as { n: number }).n;
}

export async function reprocessarCapturasFalhadas(): Promise<number> {
  const base = await getBffUrl();
  const r = await fetch(`${base}/captures/retry-failed`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!r.ok) throw new Error(`erro ${r.status}`);
  return ((await r.json()) as { requeued: number }).requeued;
}
