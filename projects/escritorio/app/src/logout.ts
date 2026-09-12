// Sair do app não pode depender do servidor.
//
// O bug que isto fecha: o logout chamava `unregisterDevice` ANTES de `clearToken`.
// O JWT dura 30 dias (jwt_ttl_hours=720); no dia 31 o `unregisterDevice` responde
// 401, a exceção pulava o `clearToken`, e o app ficava travado — todas as telas em
// "erro 401" e o botão Sair sem sair. A única saída era limpar os dados pelo Android.
// Só se manifesta com push token registrado, ou seja, exatamente no dev build.
//
// Regra: avisar o servidor é BEST-EFFORT; limpar a sessão local é garantido. Quando
// o aviso falha, `serverOk: false` deixa a tela dizer a verdade (o servidor pode
// seguir mandando push) em vez de fingir que nada aconteceu.

// E o segundo bug, mesmo lugar: o `fetch` do React Native não expira. Um servidor
// que aceita a conexão e não responde (VPS travado, proxy segurando) deixava o
// "Sair" girando pra sempre. Agora o aviso ao servidor tem prazo — vencido, conta
// como `serverOk: false` e a saída segue.

// Os módulos puros deste app só importam TIPOS uns dos outros: o `node --test` roda
// o .ts direto, sem resolver import sem extensão. Por isso o prazo mora aqui e não
// vem de `prazo.ts` (que faz o mesmo pro boot, em `App.tsx`).
function comPrazo<T>(
  executar: (signal: AbortSignal) => Promise<T>,
  ms: number,
  rotulo: string,
): Promise<T> {
  // O prazo ABORTA o request, não só para de esperar: um DELETE que sobrevivesse
  // ao "Sair" seria inofensivo, mas o padrão é o mesmo do boot (`prazo.ts`).
  const controle = new AbortController();
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      controle.abort();
      reject(new Error(`${rotulo}: sem resposta em ${ms}ms`));
    }, ms);
    executar(controle.signal).then(
      (v) => {
        clearTimeout(timer);
        resolve(v);
      },
      (e) => {
        clearTimeout(timer);
        reject(e);
      },
    );
  });
}

export type LogoutSteps = {
  /** Token de push REGISTRADO neste aparelho, ou null se não há. Nunca pede
   * permissão aqui: sair não é hora de abrir diálogo do sistema. */
  pushToken: () => Promise<string | null>;
  unregisterDevice: (token: string, signal: AbortSignal) => Promise<unknown>;
  disableLocalPush: () => Promise<unknown>;
  clearToken: () => Promise<unknown>;
  /** Prazo (ms) pro aviso ao servidor. Default 5s. */
  prazoMs?: number;
};

const PRAZO_DEFAULT_MS = 5000;

export async function performLogout(
  steps: LogoutSteps,
): Promise<{ serverOk: boolean }> {
  let serverOk = true;
  const prazo = steps.prazoMs ?? PRAZO_DEFAULT_MS;

  try {
    const token = await steps.pushToken();
    if (token) {
      await comPrazo((signal) => steps.unregisterDevice(token, signal), prazo, "sair: remover push");
    }
  } catch {
    serverOk = false;
  }

  try {
    await steps.disableLocalPush();
  } catch {
    serverOk = false;
  }

  await steps.clearToken();
  return { serverOk };
}
