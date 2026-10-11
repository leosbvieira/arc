// Distingue "não saiu do aparelho" de "o servidor respondeu com erro".
//
// A garantia "nada se perde" da SPEC valia só para a CAPTURA: a fila offline cobre
// `capture` e `session`. Concluir uma tarefa no metrô mostrava um Alert e a ação
// evaporava — a execução não tinha a mesma rede de segurança que o registro.
//
// Por que a distinção importa: enfileirar tudo seria pior que não enfileirar nada.
// - `erro 404` → a tarefa não existe; reenviar amanhã não conserta e polui a fila.
// - `erro 401` → sessão expirada; precisa de login, não de retry.
// - `erro 500` → o servidor RECEBEU e falhou. Reenviar às cegas pode concluir duas
//   vezes. É erro para mostrar, não para engolir.
//
// Só o que nem chegou ao servidor pode ser retentado com segurança.

export function ehFalhaDeRede(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  // fetch rejeita com TypeError quando o request não sai (offline, DNS, recusa).
  if (error instanceof TypeError) return true;
  // AbortController: o cliente desistiu antes de qualquer resposta.
  return error.name === "AbortError";
}

// ---------------------------------------------------------------------------
// O que fazer com um item da fila que acabou de falhar.
//
// A distinção acima existia e a fila NÃO a consultava: `_flush` fazia
// `catch { break }` — o comentário dizia "erro de rede", mas o catch não olhava o
// erro. Um item que o servidor recusa pra sempre (uma tarefa concluída na web do
// ClickUp responde 404 pra sempre) travava tudo que entrasse depois dele, sem
// contador de tentativa e sem corte por idade. A saída era limpar os dados do app,
// que apaga a fila: a lei "nada se perde" quebrada pelo mecanismo que a sustenta.
//
// Mora AQUI, e não num módulo próprio, por uma razão de runtime: `node --test` só
// roda módulo que não faz import de valor de outro `.ts` (os testados do repo só
// usam `import type`). Um `captureQueuePolicy.ts` que importasse `ehFalhaDeRede`
// não subiria no teste — e um módulo de política sem teste não conserta nada.

/** Tentativas de ENTREGA antes de um item sair da fila. Só conta recusa do servidor:
 * falha de rede não gasta tentativa, senão uma semana offline aposentaria a fila. */
export const MAX_TENTATIVAS = 5;

export type DecisaoDaFila =
  /** Nada saiu do aparelho. Para tudo e tenta depois — a fila está intacta. */
  | "esperar_rede"
  /** 401: não é este item, é a sessão. Todo o resto responderia igual, então drenar
   *  só queimaria tentativa à toa. Não conta como tentativa. */
  | "esperar_login"
  /** O servidor recusou ESTE item. Vai pro fim da fila pra não bloquear os outros. */
  | "recolocar_no_fim"
  /** Recusado vezes demais. Sai da fila (pro escaninho) pra ela poder drenar. */
  | "desistir";

/** `erro 404` -> 404; qualquer outra coisa -> null.
 *
 * O contrato é o do `api.ts`, onde toda rota lança `new Error(\`erro ${status}\`)`.
 * Frágil de propósito: no dia em que alguém mudar o formato, o teste daqui cai junto. */
export function statusDoErro(erro: unknown): number | null {
  if (!(erro instanceof Error)) return null;
  const m = /^erro (\d{3})$/.exec(erro.message);
  return m ? Number(m[1]) : null;
}

export function decidirAposFalha(
  erro: unknown,
  tentativasFeitas: number,
  limite: number = MAX_TENTATIVAS,
): DecisaoDaFila {
  if (ehFalhaDeRede(erro)) return "esperar_rede";
  const status = statusDoErro(erro);
  if (status === 401) return "esperar_login";
  // 409 = a MESMA client_key já existe no BFF com outro conteúdo. Reenviar o mesmo
  // par nunca muda a resposta; cinco voltas só atrasariam a fila. Vai direto pro
  // escaninho, onde o Leo vê o texto.
  if (status === 409) return "desistir";
  return tentativasFeitas >= limite ? "desistir" : "recolocar_no_fim";
}

/** A decisão para a drenagem inteira, em vez de só mexer neste item. */
export function paraAFila(d: DecisaoDaFila): boolean {
  return d === "esperar_rede" || d === "esperar_login";
}

/** O que a tela diz quando o servidor RESPONDEU e recusou.
 *
 * Nunca "sem conexão": havia conexão, e chamar recusa de queda foi o que mandou
 * captura boa pra uma fila travada. Cada frase diz o que fazer, porque as saídas
 * são diferentes — entrar de novo, conferir, ou reescrever. */
export function mensagemDaRecusa(erro: unknown): string {
  const status = statusDoErro(erro);
  if (status === 401) return "sessão expirada — entre de novo e mande outra vez";
  if (status !== null && status >= 500) {
    return "o servidor recebeu e falhou — confira na triagem antes de mandar de novo";
  }
  if (status !== null) return `o servidor recusou (erro ${status}) — o texto continua aqui`;
  return "não deu pra mandar — o texto continua aqui";
}
