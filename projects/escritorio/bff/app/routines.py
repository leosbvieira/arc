"""Rotinas do scorecard binário (spec §4) — DADO, não config (P2 item 2).

Antes este arquivo ERA a rotina: um dict hardcoded de strings. Agora ele é só o
domínio puro — semente, slug, dias da semana, filtro. A lista real do Leo mora na
tabela `routines` (store.py) e é editada pelo app.

Três invariantes que este módulo protege:

1. **`slug` é a chave do histórico.** `routine_checks.rotina` guarda o slug; renomear
   uma rotina (`nome`) NUNCA pode mexer nele, senão o scorecard perde o passado.
2. **`passos` são roteiro, não checks.** Existem pra ele não pular produto no skincare.
   Quem conta no scorecard — e na punição — é o item PAI, binário (decisão do Leo, 12/jul).
3. **`origem`** separa a semente (`exemplo`) do que é dele (`leo`): o sistema semeia uma
   vez, num banco vazio, e nunca mais escreve por cima.
"""
import re
import unicodedata
from datetime import date

TODOS = "*"

# Ordem de exibição dos blocos do dia (o fechamento das 21h respeita isto).
BLOCOS: tuple[str, ...] = ("manha", "dia", "noite")
BLOCO_ORDEM: dict[str, int] = {b: i for i, b in enumerate(BLOCOS)}

# Índice = date.weekday() (0=segunda). pt-BR minúsculo, sem acento.
DIAS: tuple[str, ...] = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")

TEMPLATES: tuple[str, ...] = ("yoga", "corrida")

# Semente (só num banco vazio — ver store.init_db). NADA aqui é normativo: são
# exemplos de partida. Os 7 primeiros slugs são exatamente os que já existiam no
# ROUTINES hardcoded, pra não órfãozar os checks já gravados em routine_checks.
# A ordem da lista é a `ordem` — e é ela que garante a regra do Leo: no dia corrida,
# a corrida vem SEMPRE depois da academia.
SEED: list[tuple[str, str, str, str, str, list[str]]] = [
    # (slug, nome, bloco, dias, templates, passos)
    ("acordar-5h30", "acordar 5h30", "manha", "*", "*", []),
    ("pesagem", "pesagem", "manha", "*", "*", []),
    ("skincare", "skincare AM", "manha", "*", "*",
     ["limpeza", "hidratante", "protetor solar"]),
    ("yoga", "yoga", "manha", "*", "yoga", []),
    ("meditacao", "meditação", "manha", "*", "yoga", []),
    ("academia", "academia", "manha", "*", "*", []),
    ("corrida", "corrida", "manha", "*", "corrida", []),
    ("skincare-pm", "skincare PM", "noite", "*", "*",
     ["limpeza", "sérum", "hidratante"]),
    ("diario", "diário", "noite", "*", "*", []),
    ("leitura-noturna", "leitura", "noite", "*", "*", []),
    ("mascara", "máscara", "noite", "qua", "*", []),
    ("arrumar-casa", "arrumar a casa", "dia", "dom", "*", []),
]


def _fold(s: str) -> str:
    """NFKD → tira acento → casefold. Mesma dobra usada em tasks._norm."""
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).casefold().strip()


def slugify(nome: str) -> str:
    """'Skincare da manhã!' → 'skincare-da-manha'. Vazio/só símbolos → 'rotina'
    (o slug é PK lógica; nunca pode sair string vazia daqui)."""
    s = re.sub(r"[^a-z0-9]+", "-", _fold(nome)).strip("-")
    return s or "rotina"


def _csv(value: str) -> list[str]:
    return [_fold(p) for p in (value or "").split(",") if p.strip()]


def dia_sigla(d: date) -> str:
    """date.weekday() → 'seg'..'dom'."""
    return DIAS[d.weekday()]


def vale_no_dia(routine: dict, d: date) -> bool:
    dias = (routine.get("dias") or TODOS).strip()
    return dias == TODOS or dia_sigla(d) in _csv(dias)


def vale_no_template(routine: dict, template: str | None) -> bool:
    """`template=None` = o toque das 5h30 ainda não veio: o sistema NÃO sabe se é dia
    yoga ou dia corrida, então só valem as rotinas que independem do template. Ele não
    inventa um dia que o Leo não escolheu (e a corrida não some do dia dele por default)."""
    templates = (routine.get("templates") or TODOS).strip()
    if template is None:
        return templates == TODOS
    return templates == TODOS or _fold(template) in _csv(templates)


def do_dia(rotinas: list[dict], d: date, template: str | None) -> list[dict]:
    """Filtra as rotinas ativas que valem NAQUELE dia, naquele template.

    Preserva a ordem de entrada (store.list_routines já ordena por bloco/ordem/id),
    então a corrida continua depois da academia.
    """
    return [
        r for r in rotinas
        if vale_no_dia(r, d) and vale_no_template(r, template)
    ]


# --- normalização de entrada (o app manda; a gente valida fail-closed) -------


def norm_bloco(value: str) -> str:
    bloco = _fold(value)
    if bloco not in BLOCOS:
        raise ValueError(f"bloco inválido; use {list(BLOCOS)}")
    return bloco


def norm_dias(value: str) -> str:
    """'*' (todo dia) ou csv de seg..dom. Normaliza, deduplica e reordena pela semana."""
    if value is None or not value.strip() or value.strip() == TODOS:
        return TODOS
    dias = _csv(value)
    invalidos = [d for d in dias if d not in DIAS]
    if invalidos:
        raise ValueError(f"dia inválido {invalidos}; use {list(DIAS)} ou '*'")
    return ",".join(d for d in DIAS if d in set(dias))


def norm_templates(value: str) -> str:
    """'*' (vale nos dois) ou csv de yoga/corrida."""
    if value is None or not value.strip() or value.strip() == TODOS:
        return TODOS
    templates = _csv(value)
    invalidos = [t for t in templates if t not in TEMPLATES]
    if invalidos:
        raise ValueError(f"template inválido {invalidos}; use {list(TEMPLATES)} ou '*'")
    if set(templates) == set(TEMPLATES):
        return TODOS
    return ",".join(t for t in TEMPLATES if t in set(templates))


def norm_passos(value: list[str]) -> list[str]:
    """Lista ORDENADA de rótulos. Descarta vazios; preserva acento e caixa (é display)."""
    return [p.strip() for p in (value or []) if p and p.strip()]
