"""Bloco compacto de estado do sistema para as conversas com o Hermes.

O buraco que isto fecha: `chat()` mandava `MODE_FRAME + texto do usuário` e nada
mais. O agente chamado "Mentor do Leo: accountability afiada" não via uma única
tarefa atrasada, ponto ou rotina — enquanto a tela promete, literalmente, "Pense
com alguém que conhece o sistema". Perguntar "o que merece meu foco agora?" com 4
tarefas vencidas devolvia um texto genérico de coach.

Três regras:

1. **Compacto.** Vai em toda mensagem: teto de linhas e de caracteres, com as
   atrasadas cortadas nas mais antigas (que são as que doem).
2. **Nunca derruba o chat.** Fonte fora do ar degrada para uma linha dizendo isso;
   um Mentor sem contexto ainda serve, um chat que dá 502 não.
3. **Conteúdo real.** Isto roda atrás do login, na tela do Leo — é o mesmo critério
   do digest, que neutraliza no Telegram/push (`body_telegram`) e mantém o texto
   inteiro no app (`body_app`). A lei 7 protege preview e log, não a conversa dele
   com o próprio agente.
"""
import logging

from . import pontos, tasks

logger = logging.getLogger(__name__)

MAX_ATRASADAS = 6


async def montar() -> str:
    linhas: list[str] = ["<estado_do_sistema>"]

    try:
        # Passa pelo _display: é o ponto único onde days_overdue e severidade nascem,
        # então o Mentor vê exatamente o mesmo número que a tela do Leo.
        src, _ = await tasks._source()
        abertas = [tasks._display(t) for t in src]
        atrasadas = sorted(
            (t for t in abertas if t.days_overdue is not None and t.days_overdue >= 0),
            key=lambda t: t.days_overdue,
            reverse=True,
        )
        if atrasadas:
            linhas.append(f"Atrasadas ({len(atrasadas)}):")
            for t in atrasadas[:MAX_ATRASADAS]:
                linhas.append(f"- {t.name} [{t.area}] há {t.days_overdue}d")
            if len(atrasadas) > MAX_ATRASADAS:
                linhas.append(f"- (+{len(atrasadas) - MAX_ATRASADAS} outras)")
        else:
            linhas.append("Nenhuma tarefa atrasada.")
    except Exception as exc:  # noqa: BLE001 — contexto é best-effort
        logger.warning("contexto do mentor sem tarefas: %s", type(exc).__name__)
        linhas.append("Tarefas: fonte indisponível agora.")

    try:
        p = pontos.resumo()
        ciclo = p.get("ciclo") or {}
        linhas.append(
            f"Placar: nível {p.get('nivel')} · {p.get('saldo_total')} pts · "
            f"ciclo {ciclo.get('indice')} semana {ciclo.get('semana')}/{ciclo.get('de')}"
        )
        padroes = (p.get("semana") or {}).get("padroes") or []
        if padroes:
            nomes = ", ".join(f"{pd['nome']} ({pd['furos']} furos)" for pd in padroes[:3])
            linhas.append(f"Rotinas em padrão: {nomes}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("contexto do mentor sem placar: %s", type(exc).__name__)

    linhas.append("</estado_do_sistema>")
    return "\n".join(linhas)
