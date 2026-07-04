import * as SecureStore from "expo-secure-store";

const KEY = "session_token";

// IP da máquina na Wi-Fi (detectado). Se o IP mudar (outra rede/DHCP), atualize:
// `ipconfig` → IPv4 do adaptador Wi-Fi. NÃO use "localhost" (no celular é o próprio telefone).
export const BFF_URL = "http://192.168.80.109:8000";

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
  const r = await fetch(`${BFF_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!r.ok) throw new Error("senha incorreta");
  const data = (await r.json()) as { token: string };
  await setToken(data.token);
  return data.token;
}

export async function capture(text: string): Promise<string> {
  const token = await getToken();
  const r = await fetch(`${BFF_URL}/capture`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ text }),
  });
  if (!r.ok) throw new Error(`erro ${r.status}`);
  const data = (await r.json()) as { reply: string };
  return data.reply;
}

export async function registerDevice(expoToken: string): Promise<void> {
  const token = await getToken();
  await fetch(`${BFF_URL}/devices`, {
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
  const r = await fetch(`${BFF_URL}/tasks`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`erro ${r.status}`);
  return (await r.json()) as TasksByArea;
}

export async function createTask(name: string, area: string): Promise<void> {
  const r = await fetch(`${BFF_URL}/tasks`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ name, area }),
  });
  if (!r.ok) throw new Error(`erro ${r.status}`);
}

export async function completeTask(id: string): Promise<void> {
  const r = await fetch(`${BFF_URL}/tasks/${id}/complete`, {
    method: "POST",
    headers: await authHeaders(),
  });
  if (!r.ok) throw new Error(`erro ${r.status}`);
}

// ---- Digest / Revisão (T-A7) ----
export type Digest = { count: number; text: string; body: string; tasks: Task[] };

export async function getDigest(): Promise<Digest> {
  const r = await fetch(`${BFF_URL}/digest`, { headers: await authHeaders() });
  if (!r.ok) throw new Error(`erro ${r.status}`);
  return (await r.json()) as Digest;
}
