// Frases da fatia 2: terminar uma obra agora cria a tarefa de resumão no ClickUp.
//
// Puro de propósito (sem fetch, sem relógio, sem import de valor): é o padrão de
// `chatError.ts`, `shelfView.ts` e `triagemResultado.ts`, e é o que deixa testar com
// `node --test`.

export type DesfechoDoTermino = {
  readonly titulo: string;
  readonly resumoTaskId: string | null;
};

export function mensagemDeTermino(desfecho: DesfechoDoTermino): string {
  // Ciclo sem sessão nenhuma não gera tarefa — e é assim que ele tira da estante uma
  // obra criada por engano. Prometer um resumão que não existe seria pior que calar.
  if (desfecho.resumoTaskId === null) {
    return `${desfecho.titulo} saiu da estante. Não havia sessão para resumir.`;
  }
  return `${desfecho.titulo} saiu da estante. O resumão está no Staging, esperando você triar.`;
}

export function mensagemDeTerminoFalho(detalhe: string | null): string {
  switch (detalhe) {
    case "book_com_sessao_aberta":
      return "termine a sessão de leitura desta obra antes";
    case "book_ja_terminado":
      return "esta obra já tinha saído da estante";
    case "book_terminando":
      // Não é erro do gesto dele: é a obra reservada de uma tentativa anterior.
      return "esta obra está fechando — toque em resolver para saber como ficou";
    case "book_reserva_perdida":
      // A obra saiu de "fechando" no meio do caminho — outra aba reconciliou, ou ela
      // foi reaberta. A tarefa pode ter nascido: mandar tentar de novo criaria a
      // segunda. Recarregar e olhar é a única resposta honesta.
      return "o estado da obra mudou no meio — recarregue a estante e veja como ela ficou";
    case "book_resumao_indisponivel":
      // O caso que a reserva existe para cobrir. A frase precisa dizer que a obra
      // NÃO voltou para a estante, senão ele tenta de novo e cria um segundo resumão.
      return "não deu para falar com o ClickUp. A obra ficou reservada — resolva por lá em vez de terminar de novo";
    default:
      return "não deu para terminar a obra";
  }
}

export function mensagemDeReconciliacao(
  resultado: "terminado" | "liberado",
  titulo: string,
): string {
  if (resultado === "terminado") {
    return `O resumão de ${titulo} já existia no Staging. A obra saiu da estante.`;
  }
  return `Nenhum resumão foi criado. ${titulo} voltou para a estante.`;
}

/** Quantas obras estão presas fechando, na frase que cabe num aviso de uma linha. */
export function avisoDeObrasPresas(quantas: number): string | null {
  if (quantas <= 0) return null;
  return quantas === 1
    ? "1 obra ficou fechando sem resposta do ClickUp"
    : `${quantas} obras ficaram fechando sem resposta do ClickUp`;
}
