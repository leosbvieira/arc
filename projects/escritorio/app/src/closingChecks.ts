// Montagem do payload de checks do fechamento das 21h.
//
// O bug que isto fecha: a tela mandava TODAS as rotinas do dia, com `false` para
// tudo que não estivesse marcado na tela. Como `/closing/routines` não devolvia o
// estado do dia, a tela nascia em branco e o `record_checks` (INSERT OR REPLACE)
// sobrescrevia o que tinha sido marcado de manhã — a yoga feita às 6h virava furo
// às 22h, envenenando pontos, scorecard e a punição por padrão.
//
// Duas regras, e as duas importam:
//
// 1. O estado inicial vem do SERVIDOR (`feito`), não de uma reconstrução parcial
//    no cliente: é a única fonte que conhece o dia inteiro, e não só a manhã.
// 2. Rotina sem decisão NÃO entra no payload. `pontos.py` trata linha ausente como
//    "não registrado" e não como furo (lei 4), então omitir é o que impede o
//    fechamento honesto de ser autoincriminação: hoje, marcar o dia ruim gera furo
//    e ignorar o app não gera nada — o incentivo aponta para abandonar o sistema.
//
// Desmarcar continua funcionando: uma decisão explícita `false` viaja normalmente.

export type ClosingDecisions = Record<string, boolean>;

/** Estado inicial da tela: decidido = o que o servidor já registrou como feito. */
export function seedDecisions(
  routines: Array<{ slug: string; feito?: boolean }>,
): ClosingDecisions {
  const decisions: ClosingDecisions = {};
  for (const routine of routines) {
    if (routine.feito) decisions[routine.slug] = true;
  }
  return decisions;
}

/** Só as rotinas do dia sobre as quais existe decisão explícita. */
export function buildClosingChecks(
  routines: Array<{ slug: string }>,
  decisions: ClosingDecisions,
): Array<{ rotina: string; feito: boolean }> {
  return routines
    .filter((routine) => routine.slug in decisions)
    .map((routine) => ({ rotina: routine.slug, feito: decisions[routine.slug] }));
}
