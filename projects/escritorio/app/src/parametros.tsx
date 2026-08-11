// O ÚNICO dono dos parâmetros do app: busca, valida, cacheia e revalida.
// Nenhuma tela faz fetch disto por conta própria -- nem a wiki.
import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { AppState } from "react-native";

import { getParametros } from "./api";
import {
  DEFAULT_PARAMS, Fonte, Params, PortaCache, aplicar, decidir,
} from "./parametrosCore";
import { deleteItemAsync, getItemAsync, setItemAsync } from "./storage";

const CHAVE = "wiki_parametros_v1";

const porta: PortaCache = {
  async ler() {
    const cru = await getItemAsync(CHAVE);
    if (!cru) return null;
    try { return JSON.parse(cru); } catch { return null; }
  },
  gravar: (v) => setItemAsync(CHAVE, JSON.stringify(v)),
  apagar: () => deleteItemAsync(CHAVE),
};

const Ctx = createContext<{ fonte: Fonte; revalidar: () => void }>({
  fonte: { tipo: "padrao", params: DEFAULT_PARAMS },
  revalidar: () => {},
});

export function ParametrosProvider({ children }: { children: React.ReactNode }) {
  const [fonte, setFonte] = useState<Fonte>({ tipo: "padrao", params: DEFAULT_PARAMS });

  const buscar = useCallback(async () => {
    const resposta = await getParametros();
    const cache = await porta.ler();
    const decisao = decidir({
      resposta: resposta.ok
        ? { ok: true, corpo: resposta.corpo }
        : { ok: false, status: resposta.status },
      cache,
    });
    await aplicar(decisao, porta);
    // Nenhum `if` aqui, de propósito: a política inteira é de `decidir`,
    // inclusive cair no embutido. Provider que decide é provider com política.
    setFonte(decisao.fonte);
  }, []);

  useEffect(() => { void buscar(); }, [buscar]);

  useEffect(() => {
    const sub = AppState.addEventListener("change", (s) => { if (s === "active") void buscar(); });
    return () => sub.remove();
  }, [buscar]);

  return <Ctx.Provider value={{ fonte, revalidar: () => void buscar() }}>{children}</Ctx.Provider>;
}

export function useParametros(): Fonte {
  return useContext(Ctx).fonte;
}

export function useRevalidar(): () => void {
  return useContext(Ctx).revalidar;
}

/** Atalho para quem só quer os números. `indisponivel` cai no embutido. */
export function useParams(): Params {
  const f = useParametros();
  return "params" in f ? f.params : DEFAULT_PARAMS;
}
