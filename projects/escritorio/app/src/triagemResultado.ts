// A triagem dizia "0 movidas · 1 não movida" e parava aí. O BFF manda, por tarefa, um
// campo `erro` com a causa — `tasks.aplicar_triagem` monta `{task_id, ok, erro}` e isola
// a falha de cada uma —, mas a tela contava os `ok` e derivava o resto por subtração,
// então a resposta que explicava o problema era descartada na hora de desenhar o alerta.
//
// Puro de propósito (sem fetch, sem relógio, sem import de valor): é o padrão de
// `chatError.ts` e `mesaView.ts`, e é o que deixa testar com `node --test`.

export type ResultadoTriagem = {
  readonly task_id: string;
  readonly ok: boolean;
  readonly erro: string | null;
  // `null` = ele não pediu prazo. O movimento e a data são desfechos separados de
  // propósito: mover não tem desfazer, então uma data que falha não pode marcar como
  // não movida uma tarefa que moveu — mas também não pode sumir.
  readonly prazo?: "ok" | "falhou" | null;
};

// O BFF expõe DE PROPÓSITO só o nome da classe da exceção (`type(exc).__name__`),
// nunca a mensagem: mensagem de erro remoto carrega conteúdo da tarefa, e conteúdo
// não pode vazar para log nem para tela de aviso. Traduzir aqui é o que sobra.
function causaEmPortugues(erro: string | null): string {
  // `ok: false` com `erro: null` não deveria acontecer, mas se acontecer a linha não
  // pode sumir — uma falha sem causa ainda é uma falha que ele precisa ver.
  if (erro === null) return "falha sem causa informada";
  switch (erro) {
    case "fora_do_staging":
      // A trava de `tasks.py`: a proposta é velha e a tarefa já saiu da fila.
      return "já tinha saído do Staging";
    case "nao_encontrado":
      return "não existe mais";
    case "HTTPStatusError":
      // O caso provável e o único acionável: o ClickUp não tem endpoint de mover, então
      // o BFF adiciona no destino e remove da origem — e isso exige o ClickApp ligado.
      return 'o ClickUp recusou o movimento (o ClickApp "Tasks in Multiple Lists" precisa estar ligado no workspace)';
    case "ConnectError":
    case "ConnectTimeout":
    case "ReadTimeout":
    case "TimeoutException":
      return "não deu para falar com o ClickUp";
    default:
      // Só ecoa o valor quando ele PARECE código — nome de classe ou snake_case. Se um
      // dia o BFF passar a mandar a mensagem inteira da exceção, ela carrega o título da
      // tarefa junto, e título de tarefa não vai para tela de aviso (lei 7).
      return /^[A-Za-z][A-Za-z0-9_]*$/.test(erro)
        ? `falha inesperada (${erro})`
        : "falha inesperada";
  }
}

function plural(n: number, singular: string, plural_: string): string {
  return `${n} ${n === 1 ? singular : plural_}`;
}

export function resumoDaTriagem(resultados: readonly ResultadoTriagem[]): string {
  const movidas = resultados.filter((resultado) => resultado.ok).length;
  const falhas = resultados.filter((resultado) => !resultado.ok);
  // A tarefa MOVEU e o prazo não pegou. Nunca some do resumo: ele acha que marcou
  // "amanhã", a tarefa está sem data, e nada na tela desmentiria isso.
  const semPrazo = resultados.filter((resultado) => resultado.prazo === "falhou").length;

  const linhas: string[] = [];
  if (semPrazo > 0) {
    linhas.push(
      semPrazo === 1
        ? "1 moveu, mas ficou sem o prazo que você marcou."
        : `${semPrazo} moveram, mas ficaram sem o prazo que você marcou.`,
    );
  }

  if (falhas.length === 0) {
    const cabecalho = `${plural(movidas, "tarefa movida", "tarefas movidas")}.`;
    return linhas.length ? `${cabecalho}\n\n${linhas.join("\n")}` : cabecalho;
  }

  // Agrupa por causa e preserva a ORDEM DE APARIÇÃO: um lote grande com duas causas
  // diferentes vira duas linhas, não uma lista de task ids que não dizem nada a ele.
  const porCausa = new Map<string, number>();
  for (const falha of falhas) {
    const causa = causaEmPortugues(falha.erro);
    porCausa.set(causa, (porCausa.get(causa) ?? 0) + 1);
  }

  const cabecalho = `${plural(movidas, "movida", "movidas")} · ${plural(falhas.length, "não movida", "não movidas")}.`;
  for (const [causa, quantas] of porCausa) {
    linhas.push(
      porCausa.size === 1 && quantas === falhas.length ? causa : `${quantas}: ${causa}`,
    );
  }
  return `${cabecalho}\n\n${linhas.join("\n")}`;
}
