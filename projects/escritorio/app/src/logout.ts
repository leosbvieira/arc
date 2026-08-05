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

export type LogoutSteps = {
  /** Token de push registrado, ou null se não há. */
  pushToken: () => Promise<string | null>;
  unregisterDevice: (token: string) => Promise<unknown>;
  disableLocalPush: () => Promise<unknown>;
  clearToken: () => Promise<unknown>;
};

export async function performLogout(
  steps: LogoutSteps,
): Promise<{ serverOk: boolean }> {
  let serverOk = true;

  try {
    const token = await steps.pushToken();
    if (token) await steps.unregisterDevice(token);
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
