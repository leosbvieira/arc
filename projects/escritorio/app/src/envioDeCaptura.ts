// O envio de UMA captura pela tela, sem nenhum import — só `deps`. Mesmo motivo do
// `filaDrenagem.ts`: a tela importa expo e não sobe no `node --test`, e a ordem das
// operações aqui É o conserto, então precisa de teste.
//
// Antes: flush → POST direto → só em falha de rede `enqueue`. Matar o app durante o
// POST perdia texto e client_key (revisão Claude x Codex, 11/09/2026).
// Agora: flush (ordem) → GRAVA na fila → POST → apaga da fila. O pior caso passa a ser
// duplicata de envio com a MESMA client_key, que o BFF resolve devolvendo o id
// existente.

export type ParouEm = "rede" | "login" | null;

export type DepsDoEnvio<Reply> = {
  /** Drena o que já esperava. Devolve por que parou (se parou) e quantos foram recusados. */
  flush: () => Promise<{ parou: ParouEm; rejeitados: number }>;
  /** Grava o item; devolve o id da fila. */
  enqueue: (item: { kind: "capture"; payload: any; ts: number }) => Promise<string>;
  /** Tira o item da fila depois que o POST direto respondeu. */
  removeQueued: (id: string) => Promise<boolean>;
  /** O POST direto. */
  capture: (text: string, clientKey: string, sensivel: boolean) => Promise<Reply>;
  ehFalhaDeRede: (erro: unknown) => boolean;
};

export type ResultadoDoEnvio<Reply> =
  | { tipo: "enviado"; reply: Reply; rejeitados: number }
  /** Ficou no aparelho, reenvio automático (rede) ou após login. */
  | { tipo: "guardado"; motivo: "rede" | "login"; rejeitados: number }
  /** O servidor respondeu e recusou; o texto fica na caixa, nada na fila. */
  | { tipo: "recusado"; erro: unknown; rejeitados: number };

export async function enviarCaptura<Reply>(
  deps: DepsDoEnvio<Reply>,
  entrada: { text: string; clientKey: string; sensivel: boolean; ts: number },
): Promise<ResultadoDoEnvio<Reply>> {
  const item = {
    kind: "capture" as const,
    payload: { text: entrada.text, client_key: entrada.clientKey, sensivel: entrada.sensivel },
    ts: entrada.ts,
  };

  // Drena antes pra manter a ordem: uma captura nova não passa na frente do que já
  // esperava. O desvio depende de `parou`, não de `restantes` — a fila pode ter
  // sobra com rede boa (recusados), e isso não é "sem conexão".
  const { parou, rejeitados } = await deps.flush();
  if (parou) {
    await deps.enqueue(item);
    return { tipo: "guardado", motivo: parou, rejeitados };
  }

  // GRAVA ANTES DE ENVIAR. É a única linha que muda o pior caso de "perdeu" para
  // "reenvia com a mesma chave".
  const id = await deps.enqueue(item);
  try {
    const reply = await deps.capture(entrada.text, entrada.clientKey, entrada.sensivel);
    await deps.removeQueued(id);
    return { tipo: "enviado", reply, rejeitados };
  } catch (erro) {
    if (deps.ehFalhaDeRede(erro)) {
      // Já está na fila com a mesma client_key; a drenagem seguinte reenvia.
      return { tipo: "guardado", motivo: "rede", rejeitados };
    }
    // O servidor RESPONDEU e recusou. Enfileirar era o defeito antigo: 401/404 não
    // melhoram sozinhos e o 500 pode ter gravado do outro lado. Sai da fila; o texto
    // fica na caixa, onde o Leo vê.
    await deps.removeQueued(id);
    return { tipo: "recusado", erro, rejeitados };
  }
}
