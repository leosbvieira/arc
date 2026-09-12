// Reconciliação do token de push no boot autenticado, sem nenhum import — só `deps`.
//
// O que existia: `registerForPushToken()` e, se veio token, `registerDevice(token)`.
// Três buracos (revisão Claude x Codex, 11/09/2026):
// (1) ROTAÇÃO: o Expo pode trocar o token. O antigo ficava registrado no BFF, que
//     seguia mandando push pra um token morto até o recibo DeviceNotRegistered
//     podar — e, até lá, o dedupe do BFF achava que "entregou".
// (2) REVOGAÇÃO: o Leo desliga a permissão nas configurações do Android. O token
//     continua válido pro Expo, o push "entrega" (o aparelho só não mostra), o BFF
//     registra entregue=1 e o Telegram de fallback NUNCA dispara. Digest perdido em
//     silêncio. Agora o token sai do servidor quando a permissão cai.
// (3) NULL SEM MOTIVO: `null` misturava emulador, Expo Go e permissão negada. Só a
//     permissão negada justifica mexer no servidor.

export type MotivoSemToken = "emulador" | "permissao_negada" | "sem_projectId";

export type EstadoDoToken =
  | { token: string; motivo: "ok" }
  | { token: null; motivo: MotivoSemToken };

export type DepsDoSync = {
  /** O token que ESTE aparelho registrou por último no BFF (null se nunca). */
  registrado: () => Promise<string | null>;
  /** O token de agora, ou por que não há um. NÃO persiste nada. */
  atual: () => Promise<EstadoDoToken>;
  registerDevice: (token: string) => Promise<unknown>;
  unregisterDevice: (token: string) => Promise<unknown>;
  /** Grava o token como registrado — só depois que o servidor confirmou. */
  lembrar: (token: string) => Promise<unknown>;
  esquecer: () => Promise<unknown>;
};

export type ResultadoDoSync =
  | { tipo: "registrado"; token: string }
  | { tipo: "rotacionado"; token: string; anterior: string; anteriorRemovido: boolean }
  | { tipo: "revogado"; anterior: string; removidoNoServidor: boolean }
  | { tipo: "sem_push"; motivo: MotivoSemToken };

export async function sincronizarPush(deps: DepsDoSync): Promise<ResultadoDoSync> {
  const anterior = await deps.registrado();
  const estado = await deps.atual();

  if (estado.token !== null) {
    // Registra o novo ANTES de tirar o velho: entre os dois, o aparelho recebe em
    // dobro por um instante; na ordem inversa ficaria sem nada se o segundo falhar.
    await deps.registerDevice(estado.token);
    await deps.lembrar(estado.token);
    if (anterior && anterior !== estado.token) {
      let anteriorRemovido = true;
      try {
        await deps.unregisterDevice(anterior);
      } catch {
        // Fica pro recibo DeviceNotRegistered podar; o novo já está registrado.
        anteriorRemovido = false;
      }
      return { tipo: "rotacionado", token: estado.token, anterior, anteriorRemovido };
    }
    return { tipo: "registrado", token: estado.token };
  }

  if (anterior && estado.motivo === "permissao_negada") {
    // O servidor precisa saber: com o token lá, o push "entrega" e o fallback do
    // Telegram nunca acontece. Só esquece localmente depois que o servidor confirmou,
    // senão a próxima abertura não teria mais o que remover.
    try {
      await deps.unregisterDevice(anterior);
      await deps.esquecer();
      return { tipo: "revogado", anterior, removidoNoServidor: true };
    } catch {
      return { tipo: "revogado", anterior, removidoNoServidor: false };
    }
  }

  return { tipo: "sem_push", motivo: estado.motivo };
}
