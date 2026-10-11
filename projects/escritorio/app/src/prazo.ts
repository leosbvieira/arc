// Um prazo pra promessas que não têm um: o `fetch` do React Native não expira
// sozinho, e um servidor que aceita a conexão e não responde segura o chamador
// pra sempre. Onde isso doía: o "Sair" ficava travado esperando o servidor
// confirmar a remoção do push. Sair do app nunca pode depender do servidor.

export class PrazoEsgotado extends Error {
  constructor(rotulo: string, ms: number) {
    super(`${rotulo}: sem resposta em ${ms}ms`);
    this.name = "PrazoEsgotado";
  }
}

export function comPrazo<T>(promessa: Promise<T>, ms: number, rotulo: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new PrazoEsgotado(rotulo, ms)), ms);
    promessa.then(
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

/**
 * Igual ao `comPrazo`, mas o prazo também ABORTA o request. Só a rejeição não
 * bastava (revisão Codex, 12/09/2026): o fetch continuava vivo, o servidor
 * registrava o token depois do "Sair" e ninguém mais tinha a referência local
 * pra removê-lo.
 */
export function comPrazoAbortavel<T>(
  executar: (signal: AbortSignal) => Promise<T>,
  ms: number,
  rotulo: string,
): Promise<T> {
  const controle = new AbortController();
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      controle.abort();
      reject(new PrazoEsgotado(rotulo, ms));
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
