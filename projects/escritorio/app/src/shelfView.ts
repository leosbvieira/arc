// A estante é formatação — lógica pura, sem import de valor e sem relógio próprio.
// `agoraMs` entra por parâmetro: a tela é quem sabe que horas são, e o teste também.

// Estrutural de propósito: o `Book` de readingApi é atribuível a ela sem import.
export type ObraNaEstante = {
  id: number;
  titulo: string;
  pagina_atual: number | null;
  ultima_sessao: number | null; // segundos, como o servidor manda
  // Onde a leitura parou, escrito no fim da sessão anterior. `null`/ausente quando
  // a obra ainda não tem sessão, ou quando o Hermes falhou naquela — o recap é
  // best-effort e não é regenerável.
  recap?: string | null;
};

export type LinhaEstante = {
  id: number;
  titulo: string;
  detalhe: string;
  // String porque o campo de página é um TextInput; "" quando não há o que sugerir.
  paginaInicialSugerida: string;
  // `null` = não há lembrete a mostrar. A tela não renderiza a linha nesse caso, em
  // vez de reservar um espaço vazio em toda obra.
  recap: string | null;
};

const DIA_MS = 86_400_000;

function tempoRelativo(ultimaSessaoS: number, agoraMs: number): string {
  // Leitura "no futuro" (relógio do celular adiantado quando gravou) vira hoje, e
  // não "há -1 dias".
  const dias = Math.max(0, Math.floor((agoraMs - ultimaSessaoS * 1000) / DIA_MS));
  if (dias === 0) return "hoje";
  if (dias === 1) return "ontem";
  if (dias < 7) return `há ${dias} dias`;
  const semanas = Math.floor(dias / 7);
  return `há ${semanas} ${semanas === 1 ? "semana" : "semanas"}`;
}

export function montarEstante(
  obras: ObraNaEstante[],
  agoraMs: number,
): LinhaEstante[] {
  return obras.map((obra) => {
    const partes: string[] = [];
    if (obra.pagina_atual !== null) partes.push(`pág. ${obra.pagina_atual}`);
    if (obra.ultima_sessao !== null) {
      partes.push(tempoRelativo(obra.ultima_sessao, agoraMs));
    }
    return {
      id: obra.id,
      titulo: obra.titulo,
      detalhe: partes.length ? partes.join(" · ") : "ainda sem leitura",
      paginaInicialSugerida:
        obra.pagina_atual === null ? "" : String(obra.pagina_atual),
      // Normaliza ausência a UM valor: o servidor pode mandar null, e string vazia
      // chega de sessão em que o modelo devolveu nada.
      recap: obra.recap ? obra.recap : null,
    };
  });
}
