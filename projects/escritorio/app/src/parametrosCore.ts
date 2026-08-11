// Núcleo dos parâmetros do sistema: tipos, validação, política e efeito.
// Puro e sem import de valor além do schema — o teste roda em .mjs sem bundler.
//
// O schema é O validador, não um segundo lugar onde as regras estão escritas:
// `validar` caminha sobre ele. Antes havia uma implementação manual em TS e um
// teste tentando provar que as duas concordavam.
import schema from "./wiki-schema.json" with { type: "json" };

export type Rito = { slug: string; hora: string; dia: string | null };
export type Params = {
  tarifas: { rotina: number; tarefa: number; captura: number; fechamento: number; shutdown: number; despejo: number };
  punicao: { limiar_furos: number; janela: string; desconto_padrao: number; teto_semanal: number };
  niveis: { limiares: number[] };
  ciclo: { semanas: number; inicio: string };
  staging: { dias_para_alerta: number };
  shutdown: { prioridades: number };
  areas: string[];
  ritos: Rito[];
};

export type Fonte =
  | { tipo: "fresco"; params: Params }
  | { tipo: "cache"; params: Params; salvoEm: string }
  | { tipo: "padrao"; params: Params }
  | { tipo: "indisponivel"; motivo: "sem-cache" | "sessao" };

export type Decisao = { fonte: Fonte; cache: "gravar" | "manter" | "descartar" };

export type Entrada = {
  resposta: { ok: true; corpo: unknown } | { ok: false; status: number | null };
  cache: unknown;
};

export type PortaCache = {
  ler(): Promise<unknown>;
  gravar(v: unknown): Promise<void>;
  apagar(): Promise<void>;
};

// O que o app mostra antes de falar com o servidor. NÃO é uma segunda fonte
// silenciosa: vira `Fonte.padrao`, a tela avisa, e a wiki recusa.
export const DEFAULT_PARAMS: Params = {
  tarifas: { rotina: 20, tarefa: 10, captura: 5, fechamento: 80, shutdown: 30, despejo: 40 },
  punicao: { limiar_furos: 3, janela: "semana_iso", desconto_padrao: 60, teto_semanal: 200 },
  niveis: { limiares: [700, 1700, 3400, 6800] },
  ciclo: { semanas: 12, inicio: "2026-07-06" },
  staging: { dias_para_alerta: 3 },
  shutdown: { prioridades: 3 },
  areas: ["Trabalho", "Staging", "Corpo", "Saúde Mental", "Responsabilidade",
          "Finance", "Carreira", "Estudo", "Relacionamentos", "Lazer"],
  ritos: [
    { slug: "toque", hora: "05:30", dia: null },
    { slug: "checkin", hora: "08:20", dia: null },
    { slug: "jornal", hora: "08:30", dia: null },
    { slug: "digest", hora: "09:00", dia: null },
    { slug: "shutdown", hora: "19:00", dia: null },
    { slug: "closing", hora: "21:00", dia: null },
    { slug: "review", hora: "20:00", dia: "domingo" },
  ],
};

type No = {
  type?: string; properties?: Record<string, No>; required?: string[];
  items?: No; minItems?: number; enum?: unknown[]; nullable?: boolean;
};

function confere(valor: unknown, no: No): boolean {
  if (valor === null) return no.nullable === true;
  switch (no.type) {
    case "object": {
      if (typeof valor !== "object" || Array.isArray(valor)) return false;
      const obj = valor as Record<string, unknown>;
      for (const chave of no.required ?? []) if (!(chave in obj)) return false;
      for (const [chave, filho] of Object.entries(no.properties ?? {})) {
        if (chave in obj && !confere(obj[chave], filho)) return false;
      }
      return true;
    }
    case "array":
      if (!Array.isArray(valor)) return false;
      if (no.minItems !== undefined && valor.length < no.minItems) return false;
      return no.items ? valor.every((v) => confere(v, no.items as No)) : true;
    case "integer":
      return typeof valor === "number" && Number.isInteger(valor);
    case "number":
      return typeof valor === "number";
    case "string":
      return typeof valor === "string" && (!no.enum || no.enum.includes(valor));
    case "boolean":
      return typeof valor === "boolean";
    default:
      return true;
  }
}

export function validar(bruto: unknown): Params | null {
  return confere(bruto, schema as No) ? (bruto as Params) : null;
}

function doCache(cru: unknown): { params: Params; salvoEm: string } | null {
  if (!cru || typeof cru !== "object") return null;
  const env = cru as { params?: unknown; salvoEm?: unknown };
  if (typeof env.salvoEm !== "string" || Number.isNaN(Date.parse(env.salvoEm))) return null;
  const params = validar(env.params);
  return params ? { params, salvoEm: env.salvoEm } : null;
}

export function decidir(e: Entrada): Decisao {
  // Precedência: resposta válida SEMPRE grava. Só sem resposta válida o cache
  // ruim é descartado -- senão um 200 bom com cache corrompido apagaria em vez
  // de persistir.
  if (e.resposta.ok) {
    const params = validar(e.resposta.corpo);
    if (params) return { fonte: { tipo: "fresco", params }, cache: "gravar" };
  }
  const bom = doCache(e.cache);
  if (bom) return { fonte: { tipo: "cache", ...bom }, cache: "manter" };

  // Sem resposta E sem cache: 401 significa app deslogado (o fluxo de login
  // assume), qualquer outra falha cai no embutido -- rotulado `padrao`, com
  // indicador na tela, e recusado pela wiki via fonteParaWiki.
  // `decidir` produz `padrao` ELA MESMA: se o provider fizesse isso, teria
  // política própria, e política mora aqui (WIKI-SPEC §3.3).
  const status = e.resposta.ok ? null : e.resposta.status;
  const cache = e.cache == null ? "manter" : "descartar";
  if (status === 401) return { fonte: { tipo: "indisponivel", motivo: "sessao" }, cache };
  return { fonte: { tipo: "padrao", params: DEFAULT_PARAMS }, cache };
}

export async function aplicar(d: Decisao, porta: PortaCache): Promise<void> {
  // Falha de armazenamento não pode derrubar a tela: a fonte já foi decidida.
  try {
    if (d.cache === "gravar" && "params" in d.fonte) {
      await porta.gravar({ params: d.fonte.params, salvoEm: new Date().toISOString() });
    } else if (d.cache === "descartar") {
      await porta.apagar();
    }
  } catch {
    // silêncio deliberado: ver acima
  }
}

export function minutos(hora: string): number {
  const [h, m] = hora.split(":");
  return Number(h) * 60 + Number(m);
}

/** A wiki é a única tela que promete ser a referência: ela recusa o embutido. */
export function fonteParaWiki(f: Fonte): Fonte {
  return f.tipo === "padrao" ? { tipo: "indisponivel", motivo: "sem-cache" } : f;
}
