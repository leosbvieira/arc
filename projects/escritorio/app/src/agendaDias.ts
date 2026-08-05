// A faixa de dias da tela de Agenda.
//
// O buraco que isto fecha: `GET /agenda` estava implementado, aceitava `?data=` e
// NENHUMA tela chamava. A agenda real era um card dentro da Abertura (só hoje) e duas
// linhas na Home — não havia como ver amanhã, nem a semana, embora a SPEC peça
// "visão dia/semana" e o P2 item 8 esteja marcado como concluído.
//
// ⚠️ As datas vêm dos componentes LOCAIS do Date. `toISOString()` daria o dia em UTC:
// das 21h à meia-noite no Brasil isso é o dia SEGUINTE, então a faixa começaria em
// "amanhã" justamente no horário em que o Leo mais abre o app.

export type DiaDaFaixa = { data: string; rotulo: string; diaDoMes: number };

const SEMANA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];

function chave(d: Date): string {
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mes}-${dia}`;
}

/** Hoje + 6 dias. Uma semana é o horizonte útil: mais que isso vira planejamento. */
export function faixaDeDias(agora: Date = new Date()): DiaDaFaixa[] {
  const base = new Date(agora.getFullYear(), agora.getMonth(), agora.getDate());
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(base.getFullYear(), base.getMonth(), base.getDate() + i);
    return {
      data: chave(d),
      rotulo: i === 0 ? "hoje" : i === 1 ? "amanhã" : SEMANA[d.getDay()],
      diaDoMes: d.getDate(),
    };
  });
}

/** Rótulo longo do dia selecionado, para o cabeçalho da lista. */
export function rotuloDoDia(data: string, agora: Date = new Date()): string {
  const partes = /^(\d{4})-(\d{2})-(\d{2})$/.exec(data);
  if (!partes) return data;
  const d = new Date(Number(partes[1]), Number(partes[2]) - 1, Number(partes[3]));
  const hoje = new Date(agora.getFullYear(), agora.getMonth(), agora.getDate());
  const dias = Math.round((d.getTime() - hoje.getTime()) / 86400000);
  if (dias === 0) return "hoje";
  if (dias === 1) return "amanhã";
  return `${SEMANA[d.getDay()]}, ${d.getDate()}`;
}
