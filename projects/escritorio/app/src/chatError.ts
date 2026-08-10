// O Chat mostrava a falha como se fosse fala do Mentor: o `catch` de Chat.tsx põe
// `e.message` numa bolha de IA, e `chatSend` jogava `erro 502` ali. Além de feio, era
// indistinguível — cota esgotada, PC desligado e timeout viravam o mesmo "erro 502".
//
// O BFF agora manda um código no `detail` e, quando sabe, um `Retry-After`. Este módulo
// é só a tradução para frase. Puro de propósito (sem fetch, sem relógio): é o padrão de
// `offlineError.ts` e `mesaView.ts`, e é o que deixa testar com `node --test`.

export type FalhaDoChat = {
  readonly status: number;
  readonly detail: string | null;
  readonly retryAposS: number | null;
};

function quandoVolta(retryAposS: number | null): string {
  if (retryAposS === null || retryAposS <= 0) return "Tenta de novo daqui a pouco.";
  // Arredonda para CIMA: dizer "1 min" para 90s faz ele tentar cedo e falhar de novo.
  if (retryAposS < 60) return "Volta em menos de 1 min.";
  return `Volta em ~${Math.ceil(retryAposS / 60)} min.`;
}

export function mensagemDaFalhaDoChat(falha: FalhaDoChat): string {
  switch (falha.detail) {
    case "hermes_quota":
      // Não é defeito e não pede ação nenhuma dele — só espera.
      return `A cota do modelo acabou. ${quandoVolta(falha.retryAposS)}`;
    case "hermes_credencial":
      // Este PEDE ação, e é a única mensagem daqui que diz o que fazer: o `codex` CLI
      // e o Hermes dividem o mesmo refresh token, e quem refresca primeiro consome o
      // do outro. Nenhum retry resolve.
      return (
        "A credencial do Hermes foi consumida por outro cliente (o Codex CLI, " +
        "provavelmente). No PC: rode `codex` e depois `hermes auth`."
      );
    case "hermes_indisponivel":
      return "O Hermes não respondeu. O PC pode estar desligado.";
    default:
      return `Não consegui responder agora (erro ${falha.status}).`;
  }
}

export function segundosDoRetryAfter(bruto: string | null): number | null {
  // Só a forma delta-seconds, igual ao `_parse_retry_after_seconds` do Hermes. Data
  // HTTP devolve null em vez de chutar — quem chama já tem frase para "não sei quando".
  if (bruto === null) return null;
  const limpo = bruto.trim();
  // `Number("")` é 0, não NaN — sem esta guarda um header vazio virava "0 segundos".
  if (limpo === "") return null;
  const segundos = Number(limpo);
  if (!Number.isInteger(segundos) || segundos < 0) return null;
  return segundos;
}
