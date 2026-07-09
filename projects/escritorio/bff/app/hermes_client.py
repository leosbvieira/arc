"""Ponte pro Hermes real via CLI oneshot (`hermes -z "<prompt>"`).

O Hermes local NÃO expõe HTTP — ele roda como TUI/gateway e fala pra fora (ChatGPT).
O modo oneshot imprime só a resposta final no stdout, com tools/memória/SOUL carregados.
Rodamos num thread (asyncio.to_thread) porque o loop do uvicorn no Windows nem sempre
suporta subprocess assíncrono; subprocess.run num thread é à prova disso.
"""
import asyncio
import logging
import subprocess

from .config import settings

logger = logging.getLogger(__name__)

# Enquadramento por modo (o SOUL.md já define o escritório; isto só escolhe o chapéu).
MODE_FRAME = {
    "Mentor": "Você é o Mentor do Leo: accountability afiada, honesto, discorda quando precisa. Responda direto.",
    "Conselho": "Você é o Conselho do Leo: conselheiro estratégico e jurídico, advogado do diabo. Aponte riscos.",
    "Capturas": "Modo Capturas: transforme o que o Leo disser em nota/tarefa organizada e confirme onde salvou.",
    "Tarefas": "Modo Tarefas: foque em ação concreta e no ClickUp.",
    "Leitura": "Modo Captura de leitura: organize citação/comentário/ideia do que o Leo trouxe.",
}


_MENU_BULLETS = ("- tarefas", "- capturas", "- mentor", "- conselho")


def _clean(s: str) -> str:
    """Remove o bloco de menu de modos que o SOUL injeta no começo da resposta."""
    lines = s.strip().splitlines()
    i = 0
    while i < len(lines):
        t = lines[i].strip().lower()
        if t == "" or t.startswith("modos") or t.startswith("manual completo") or t.startswith(_MENU_BULLETS):
            i += 1
        else:
            break
    cleaned = "\n".join(lines[i:]).strip()
    return cleaned or s.strip()


async def capture(text: str, profile: str | None = None) -> str:
    """Manda o texto pro Hermes (com o enquadramento do modo) e devolve a resposta."""
    prof = profile or settings.hermes_profile_capture

    if settings.hermes_mock:
        return f"[mock:{prof}] anotado: {text}"

    frame = MODE_FRAME.get(prof, "")
    if not frame:
        logger.warning("profile desconhecido %r - captura segue sem frame", prof)  # sem logar o texto
    suppress = "(Responda direto ao Leo, sem exibir o menu de modos nem o manual.)"
    prompt = "\n\n".join(p for p in (frame, text, suppress) if p)

    def _run() -> subprocess.CompletedProcess:
        return subprocess.run(
            [settings.hermes_bin, "-z", prompt],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=settings.hermes_timeout,
        )

    try:
        proc = await asyncio.to_thread(_run)
    except subprocess.TimeoutExpired:
        raise RuntimeError("o Hermes demorou demais pra responder (timeout)")
    except FileNotFoundError:
        raise RuntimeError(f"não achei o hermes em '{settings.hermes_bin}' (ajuste HERMES_BIN no .env)")

    if proc.returncode != 0:
        msg = (proc.stderr or "").strip()[:300]
        raise RuntimeError(msg or f"hermes saiu com código {proc.returncode}")

    reply = _clean(proc.stdout or "")
    return reply or "(o Hermes respondeu vazio)"
