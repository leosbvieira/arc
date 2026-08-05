// Prazo da tarefa criada no app.
//
// O buraco que isto fecha: `createTask` mandava só `{name, area}`, embora o BFF
// aceite `due`/`hora` desde o P2 item 7 (com validação fail-closed, fuso e
// agendamento prontos). Consequência: toda tarefa criada no app nascia sem prazo,
// e o motor de cobrança só seleciona quem tem `due` — ou seja, nunca era cobrada e
// nunca entrava em digest nenhum. Pelo mesmo motivo a tabela `scheduler` ficou com
// ZERO linhas desde sempre: `POST /tasks` é o único caminho de usuário que agenda,
// então o ⏰ "hora marcada" nunca disparou uma vez.
//
// Sem date picker: chips de escolha rápida cobrem o caso real (hoje/amanhã/semana)
// sem obrigar a digitar data no celular.
//
// ⚠️ A data é montada a partir dos componentes LOCAIS do Date. `toISOString()` daria
// o dia em UTC — e das 21h à meia-noite no Brasil isso é o dia SEGUINTE, criando
// cobrança no dia errado exatamente no horário em que o Leo mais usa o app.

export type DueChoice = "hoje" | "amanha" | "semana" | null;

const DIAS: Record<Exclude<DueChoice, null>, number> = {
  hoje: 0,
  amanha: 1,
  semana: 7,
};

/** `YYYY-MM-DD` no fuso do aparelho, ou null quando a tarefa não tem prazo. */
export function dueFromChoice(choice: DueChoice, agora: Date = new Date()): string | null {
  if (choice === null) return null;
  const d = new Date(
    agora.getFullYear(),
    agora.getMonth(),
    agora.getDate() + DIAS[choice],
  );
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mes}-${dia}`;
}

/** Mesma regra do validador do BFF: hora civil explícita, 24h. */
export function horaValida(hora: string): boolean {
  return /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(hora);
}
