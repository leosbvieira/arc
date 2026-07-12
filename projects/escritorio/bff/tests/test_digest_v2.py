import pytest
from fastapi.testclient import TestClient

from app import store, tasks, telegram
from app.config import settings
from app.main import app, require_auth
from app.tasks import Task, render_digest_lines, routine_lines, staging_line


# ---- funções puras (verbatim do brief) -------------------------------------

def test_staging_line_por_idade():
    assert staging_line(count=4, oldest_days=5) == "📥 staging: 4 itens, mais velho 5d — triar no ClickUp"
    assert staging_line(count=2, oldest_days=1) is None
    assert staging_line(count=0, oldest_days=None) is None


def test_rotina_so_por_padrao(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    for i, feito in enumerate([False, False, False, True, True]):
        store.record_checks(f"2026-07-0{i+1}", "yoga", [("academia", feito)])
    store.record_checks("2026-07-06", "yoga", [("yoga", False)])
    lines = routine_lines(today="2026-07-07")
    assert any("academia: 3 furos em 7d." in l for l in lines)
    assert not any("yoga" in l for l in lines)              # nunca furo isolado


def test_area_sensivel_sai_neutralizada_no_telegram():
    t1 = Task(id="1", name="Marcar psiquiatra", area="Corpo", days_overdue=3, severity="firme")
    t2 = Task(id="2", name="Pagar boleto", area="Finance", days_overdue=1, severity="leve")
    lines = render_digest_lines([t1, t2], for_channel="telegram")
    joined = "\n".join(lines)
    assert "psiquiatra" not in joined                       # lei 7: lockscreen mostra tudo
    assert any("1 pendência de saúde (3d de atraso) — abre o app" in l for l in lines)
    assert any("Pagar boleto" in l for l in lines)          # nao-sensivel sai normal
    full = "\n".join(render_digest_lines([t1, t2], for_channel="app"))
    assert "Marcar psiquiatra" in full                      # no app (atras do login) sai inteiro


def test_area_sensivel_fail_closed_variantes():
    # Lei 7 fail-closed: drift de nome (caixa/acento/espaço) NÃO pode vazar no lockscreen.
    variantes = [
        Task(id="1", name="Marcar psiquiatra", area="corpo ", days_overdue=2, severity="leve"),
        Task(id="2", name="Terapia semanal", area="Saude Mental", days_overdue=1, severity="leve"),
    ]
    joined = "\n".join(render_digest_lines(variantes, for_channel="telegram"))
    assert "psiquiatra" not in joined and "Terapia" not in joined
    assert joined.count("1 pendência de saúde") == 2       # ambas neutralizadas
    full = "\n".join(render_digest_lines(variantes, for_channel="app"))
    assert "Marcar psiquiatra" in full and "Terapia semanal" in full  # app mostra inteiro


def test_age_days_guard_e_utc():
    assert tasks._age_days(None) is None
    assert tasks._age_days("0") is None
    assert tasks._age_days("nao-numero") is None           # não-int → None, não explode
    assert tasks._age_days(1609459200000) > 1500           # 2021-01-01Z: idade determinística


# ---- endpoints + integração (dedupe, persistência, gate acionável, lei 7) ---

HDR = {"X-Internal-Token": settings.internal_token}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "tasks_source", "mock")   # isola do ClickUp real do .env
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def _only(name, area, due_offset):
    """Substitui a fonte mock por uma única tarefa determinística."""
    return lambda: [tasks._Task("x", name, area, due_offset=due_offset)]


def test_run_digest_dedupe_persiste_e_neutraliza(client, monkeypatch):
    sent = []
    async def fake_send(text):
        sent.append(text)
        return True
    monkeypatch.setattr(telegram, "send", fake_send)
    monkeypatch.setattr(tasks, "_open", _only("Marcar psiquiatra", "Corpo", -3))

    r1 = client.post("/internal/run-digest", headers=HDR)
    assert r1.json() == {"count": 1, "telegram": True}
    assert len(sent) == 1 and "psiquiatra" not in sent[0]           # lei 7: nada no Telegram

    r2 = client.post("/internal/run-digest", headers=HDR)           # 2ª chamada no mesmo dia
    assert "skipped" in r2.json() and len(sent) == 1                # não reenvia (entregue hoje)

    g = client.get("/digest").json()                                # §10: reabre o run do dia
    assert g["count"] == 1 and "Marcar psiquiatra" in g["body"]     # app (atrás do login) inteiro
    assert [t["name"] for t in g["tasks"]] == ["Marcar psiquiatra"]  # tasks frescas p/ a Home


def test_falha_de_entrega_nao_consome_o_dia(client, monkeypatch):
    outcomes = iter([False, True])
    sent = []
    async def fake_send(text):
        sent.append(text)
        return next(outcomes)
    monkeypatch.setattr(telegram, "send", fake_send)
    monkeypatch.setattr(tasks, "_open", _only("Pagar boleto", "Finanças", -1))

    assert client.post("/internal/run-digest", headers=HDR).json()["telegram"] is False
    assert client.post("/internal/run-digest", headers=HDR).json()["telegram"] is True   # retry ok
    assert len(sent) == 2                                            # falha não bloqueou o retry


def test_envia_so_com_linha_extra(client, monkeypatch):
    sent = []
    async def fake_send(text):
        sent.append(text)
        return True
    monkeypatch.setattr(telegram, "send", fake_send)
    monkeypatch.setattr(tasks, "_open", lambda: [])                 # zero tarefas
    monkeypatch.setattr(tasks, "routine_lines",
                        lambda today=None: ["🔁 academia: 3 furos nos últimos 7 dias"])

    r = client.post("/internal/run-digest", headers=HDR).json()
    assert r["count"] == 0 and r["telegram"] is True               # rotina sozinha já envia (C10/C11)
    assert "academia" in sent[0]


def test_envia_so_com_staging(client, monkeypatch):
    # staging_line real é coberta pela pura test_staging_line_por_idade; o caminho vivo
    # (ClickUp) espera a lista Staging da Task 6. Aqui provamos só a fiação: linha de
    # staging sozinha (sem tarefas/rotina) já dispara envio e entra no corpo.
    sent = []
    async def fake_send(text):
        sent.append(text)
        return True
    monkeypatch.setattr(telegram, "send", fake_send)
    monkeypatch.setattr(tasks, "_open", lambda: [])
    monkeypatch.setattr(tasks, "routine_lines", lambda today=None: [])
    monkeypatch.setattr(tasks, "staging_line",
                        lambda count, oldest_days: "📥 staging: 4 itens, mais velho 5d — triar no ClickUp")

    r = client.post("/internal/run-digest", headers=HDR).json()
    assert r["count"] == 0 and r["telegram"] is True
    assert "staging" in sent[0]


def test_nada_acionavel_nao_envia(client, monkeypatch):
    sent = []
    async def fake_send(text):
        sent.append(text)
        return True
    monkeypatch.setattr(telegram, "send", fake_send)
    monkeypatch.setattr(tasks, "_open", lambda: [])
    monkeypatch.setattr(tasks, "routine_lines", lambda today=None: [])

    r = client.post("/internal/run-digest", headers=HDR).json()
    assert r == {"count": 0, "telegram": False} and sent == []      # sem linha acionável, não manda


def test_token_interno_invalido(client):
    r = client.post("/internal/run-digest", headers={"X-Internal-Token": "errado"})
    assert r.status_code == 403


async def test_capturas_travadas_viram_linha_neutra(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "tasks_source", "mock")   # isola do ClickUp real do .env
    store.init_db()
    cid = store.enqueue_capture("conteudo sensivel do leo", None)
    for _ in range(store.MAX_ATTEMPTS):
        store.mark_capture(cid, bump_attempts=True, error="HermesTimeout")
    assert store.failed_captures()                                  # a captura virou 'failed'
    monkeypatch.setattr(tasks, "_open", lambda: [])
    monkeypatch.setattr(tasks, "routine_lines", lambda today=None: [])

    result = await tasks.run_digest()
    linha = "⚠ 1 capturas não processadas — abrir o app"
    assert result["lines_extra"] == [linha]
    assert linha in result["body_telegram"] and linha in result["body_app"]
    assert "conteudo sensivel" not in result["body_telegram"]      # lei 7: sem conteúdo
