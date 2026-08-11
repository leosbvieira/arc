import type { Abertura } from "./api";

export type HomeSignals = {
  staging: number | null;
  anki: number | null;
  reading: number | null;
  /** Dias desde a última interação. >=7 dispara o Modo Retorno. */
  dias_ausente?: number;
};

export type HomeAction = {
  icon: string;
  eyebrow: string;
  title: string;
  subtitle: string;
  target: string;
};

export type HomeAgendaItem = {
  time: string;
  title: string;
  source: string;
};

type TimedReference = { hora: string; ref: string };
type CalendarReference = {
  hora: string | null;
  titulo: string;
  fonte: string;
  inicio_ts?: number | null;
};

function localDateKey(now: Date): string {
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function minuteOfDay(value: string | null): number | null {
  if (!value) return null;
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim());
  if (!match) return null;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour > 23 || minute > 59) return null;
  return hour * 60 + minute;
}

export function nextAgendaAt(
  horarios: TimedReference[],
  calendario: CalendarReference[],
  data: string,
  now = new Date(),
  limit = 2,
): HomeAgendaItem[] {
  const isToday = data === localDateKey(now);
  const currentMinute = now.getHours() * 60 + now.getMinutes();
  const nowSeconds = now.getTime() / 1000;
  const candidates = [
    ...horarios.map((item) => ({
      time: item.hora,
      title: item.ref,
      source: "horário",
      minute: minuteOfDay(item.hora),
      timestamp: null as number | null,
    })),
    ...calendario.map((item) => ({
      time: item.hora ?? "dia",
      title: item.titulo,
      source: item.fonte,
      minute: minuteOfDay(item.hora),
      timestamp: item.inicio_ts ?? null,
    })),
  ];

  return candidates
    .filter((item) => {
      if (!isToday || item.time === "dia") return true;
      if (item.timestamp !== null) return item.timestamp >= nowSeconds;
      return item.minute === null || item.minute >= currentMinute;
    })
    .sort((left, right) => {
      const leftMinute = left.time === "dia" ? -1 : left.minute ?? Number.MAX_SAFE_INTEGER;
      const rightMinute = right.time === "dia" ? -1 : right.minute ?? Number.MAX_SAFE_INTEGER;
      return leftMinute - rightMinute || left.title.localeCompare(right.title, "pt-BR");
    })
    .slice(0, Math.max(0, limit))
    .map(({ time, title, source }) => ({ time, title, source }));
}

export function actionForAt(
  abertura: Abertura | null,
  signals: HomeSignals,
  now = new Date(),
): HomeAction {
  const hour = now.getHours();
  const sunday = now.getDay() === 0;

  // MODO RETORNO — vem antes de tudo, de propósito.
  // Voltar depois de uma semana fora e receber o digest inteiro em 🚨, o "Foco de
  // hoje" lotado de atrasadas e o rito da hora como se nada tivesse acontecido é
  // exatamente a pilha de culpa que a lei 4 proíbe, no momento em que ela mais
  // machuca. Para um sistema desenhado para TDAH, é a diferença entre voltar e
  // desinstalar. Uma porta só, sem cobrança, sem placar.
  if ((signals.dias_ausente ?? 0) >= 7) {
    return {
      icon: "sunrise",
      eyebrow: "modo retorno",
      title: "Bem-vindo de volta",
      subtitle: `${signals.dias_ausente} dias fora. Comece pelo que está na cabeça agora — o resto espera.`,
      target: "capturar",
    };
  }

  if (hour < 8 && !abertura?.template) {
    return { icon: "sunrise", eyebrow: "abrir o dia", title: "Yoga ou corrida?", subtitle: "Defina o ritmo antes de negociar com o dia.", target: "abertura" };
  }
  if (hour < 12 && !abertura?.checkin.feito) {
    return { icon: "activity", eyebrow: "check-in · 60 segundos", title: "Como você chega hoje?", subtitle: "Energia, clareza e uma prioridade real.", target: "abertura" };
  }
  if ((signals.reading ?? 0) > 0 && hour < 19) {
    return { icon: "book-open", eyebrow: "sessão preservada", title: "Continuar a leitura", subtitle: `${signals.reading} sessão pendente no seu buffer.`, target: "leitura" };
  }
  if (sunday && hour >= 17) {
    return { icon: "compass", eyebrow: "review semanal", title: "Ler a semana sem fantasia", subtitle: "Números, padrões e a próxima correção de rota.", target: "revisao" };
  }
  if (hour >= 19 && hour < 21) {
    return { icon: "sunset", eyebrow: "shutdown", title: "Fechar o trabalho", subtitle: "Pendências, follow-ups e três prioridades de amanhã.", target: "shutdown" };
  }
  if (hour >= 21) {
    return { icon: "moon", eyebrow: "rito das 21h", title: "Fechar o dia", subtitle: "Uma linha, seus ritmos e nada carregado para a cama. 90 segundos.", target: "fechar" };
  }
  return { icon: "crosshair", eyebrow: "agora", title: "Executar o que importa", subtitle: "Abra o foco e conclua uma coisa antes da próxima.", target: "tarefas" };
}
