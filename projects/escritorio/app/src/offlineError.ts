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
