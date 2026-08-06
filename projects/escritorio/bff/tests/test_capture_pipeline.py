import pytest
from fastapi.testclient import TestClient

from app import capture_pipeline as cp
from app import main, store
from app.auth import require_auth
from app.config import settings


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    yield
    main.app.dependency_overrides.clear()


@pytest.fixture
def spies(monkeypatch):
    calls = {"raw": [], "clickup": [], "classify": [], "find": []}

    async def fake_raw(text, capture_id, ts=None):
        calls["raw"].append((text, capture_id))
        return f"1- Inbox/Raw/raw-c{capture_id}.md"

    async def fake_classify(text):
        calls["classify"].append(text)
        return {"tipo": "nota", "titulo": None, "quando": None}

    async def fake_find(list_id, marker):
        calls["find"].append((list_id, marker))
        return None

    async def fake_create(
        area,
        nome,
        due_ts=None,
        tags=None,
        description=None,
    ):
        calls["clickup"].append(
            {
                "area": area,
                "nome": nome,
                "due": due_ts,
                "tags": tags,
                "desc": description,
            }
        )
        return {"id": "tsk1", "name": nome}

    monkeypatch.setattr(cp.vault_client, "write_raw", fake_raw)
    monkeypatch.setattr(cp.hermes_client, "classify", fake_classify)
    monkeypatch.setattr(cp.clickup_client, "find_task_by_marker", fake_find)
    monkeypatch.setattr(cp, "_create_task", fake_create)
    return calls


async def test_nota_vira_so_raw(spies):
    store.enqueue_capture("pensamento solto sobre estoicismo", None)
    assert await cp.process_pending() == 1
    assert spies["raw"][0][0] == "pensamento solto sobre estoicismo"
    assert spies["clickup"] == []
    assert store.pending_captures() == []


async def test_conteudo_sensivel_some_do_sqlite_depois_do_raw(spies):
    segredo = "sensível: conteúdo de terapia que não deve ficar na fila"
    cid = store.enqueue_capture(segredo, None, sensivel=True)

    assert await cp.process_pending() == 1
    with store._connect() as con:
        row = con.execute(
            "SELECT text, status, raw_path FROM capture_queue WHERE id = ?",
            (cid,),
        ).fetchone()

    assert row["status"] == "done"
    assert row["text"] == ""
    assert row["raw_path"].endswith(f"raw-c{cid}.md")


async def test_toda_tarefa_vai_pra_staging_com_link_do_raw(spies, monkeypatch):
    async def classify(text):
        return {
            "tipo": "tarefa_pessoal",
            "titulo": "Comprar presente",
            "quando": None,
        }

    monkeypatch.setattr(cp.hermes_client, "classify", classify)
    cid = store.enqueue_capture("comprar presente pra mae", None)
    await cp.process_pending()

    call = spies["clickup"][0]
    assert call["area"] == "Staging"
    assert f"raw-c{cid}" in call["desc"]
    assert f"[cap:{cid}]" in call["desc"]
    assert spies["find"] == [
        (cp.clickup_client.AREA_LISTS["Staging"], f"[cap:{cid}]")
    ]


async def test_reconcilia_marker_antes_de_criar(spies, monkeypatch):
    async def classify(text):
        return {
            "tipo": "tarefa_trabalho",
            "titulo": "Enviar relatório",
            "quando": None,
        }

    async def found(list_id, marker):
        spies["find"].append((list_id, marker))
        return "tsk-existente"

    monkeypatch.setattr(cp.hermes_client, "classify", classify)
    monkeypatch.setattr(cp.clickup_client, "find_task_by_marker", found)

    cid = store.enqueue_capture("enviar relatório", None)
    await cp.process_pending()

    assert spies["clickup"] == []
    assert spies["find"] == [
        (cp.clickup_client.AREA_LISTS["Staging"], f"[cap:{cid}]")
    ]
    with store._connect() as con:
        row = con.execute(
            "SELECT status, clickup_task_id FROM capture_queue WHERE id = ?",
            (cid,),
        ).fetchone()
    assert row["status"] == "done"
    assert row["clickup_task_id"] == "tsk-existente"


async def test_cobranca_leva_tag_aguardando_e_schedule(spies, monkeypatch):
    async def classify(text):
        return {
            "tipo": "cobranca",
            "titulo": "Cobrar Yan do contrato",
            "quando": "2026-07-09 15:00",
        }

    monkeypatch.setattr(cp.hermes_client, "classify", classify)
    store.enqueue_capture("cobrar o Yan do contrato as 15h", None)
    await cp.process_pending()

    call = spies["clickup"][0]
    assert call["tags"] == ["aguardando"]
    assert call["due"] is not None
    assert len(store.due_schedules(call["due"] + 1)) == 1


async def test_schedule_retomavel_sem_duplicar_task_ou_lembrete(spies, monkeypatch):
    async def classify(text):
        return {
            "tipo": "tarefa_pessoal",
            "titulo": "Ir ao dentista",
            "quando": "2026-07-09 15:00",
        }

    monkeypatch.setattr(cp.hermes_client, "classify", classify)
    cid = store.enqueue_capture("dentista as 15h", None)
    store.mark_capture(
        cid,
        raw_path="1- Inbox/Raw/r.md",
        clickup_task_id="tsk9",
    )

    assert await cp.process_pending() == 1
    due_ts = cp._parse_quando("2026-07-09 15:00")
    assert len(store.due_schedules(due_ts + 1)) == 1
    assert spies["clickup"] == []

    # Simula outra retomada do mesmo item: nem a task nem o schedule duplicam.
    store.mark_capture(cid, status="pending")
    assert await cp.process_pending() == 1
    assert len(store.due_schedules(due_ts + 1)) == 1
    assert spies["clickup"] == []


async def test_hermes_caido_preserva_raw_e_retenta(spies, monkeypatch):
    async def boom(text):
        raise RuntimeError("timeout")

    monkeypatch.setattr(cp.hermes_client, "classify", boom)
    store.enqueue_capture("nada se perde", None)

    await cp.process_pending()
    # A falha agenda a próxima tentativa: o item não volta na rodada seguinte, senão
    # 25s de instabilidade queimariam as 5 tentativas.
    assert store.pending_captures() == []
    with store._connect() as con:
        con.execute("UPDATE capture_queue SET proxima_em = 0")
        con.commit()
    row = store.pending_captures()[0]
    assert row["raw_path"]
    assert row["attempts"] == 1
    assert "nada se perde" not in (row["last_error"] or "")

    await cp.process_pending()
    assert len(spies["raw"]) == 1


async def test_classify_invalido_degrada_para_nota(spies, monkeypatch):
    async def classify(text):
        return {
            "tipo": "alucinado",
            "titulo": None,
            "quando": None,
        }

    monkeypatch.setattr(cp.hermes_client, "classify", classify)
    store.enqueue_capture("qualquer coisa", None)
    await cp.process_pending()
    assert spies["clickup"] == []
    assert store.pending_captures() == []


async def test_verdict_malformado_degrada_para_nota(spies, monkeypatch):
    async def classify(text):
        return {"tipo": [], "titulo": 123, "quando": {}}

    monkeypatch.setattr(cp.hermes_client, "classify", classify)
    cid = store.enqueue_capture("fallback seguro", None)

    assert await cp.process_pending() == 1
    assert spies["clickup"] == []
    with store._connect() as con:
        row = con.execute(
            "SELECT status FROM capture_queue WHERE id = ?",
            (cid,),
        ).fetchone()
    assert row["status"] == "done"


async def test_ja_criado_no_clickup_nao_duplica(spies, monkeypatch):
    async def classify(text):
        return {
            "tipo": "tarefa_pessoal",
            "titulo": "X",
            "quando": None,
        }

    monkeypatch.setattr(cp.hermes_client, "classify", classify)
    cid = store.enqueue_capture("x", None)
    store.mark_capture(
        cid,
        raw_path="r.md",
        clickup_task_id="tsk9",
    )
    await cp.process_pending()
    assert spies["clickup"] == []
    assert spies["find"] == []


def test_parse_quando_degrada_para_none_em_lixo():
    assert cp._parse_quando(None) is None
    assert cp._parse_quando(123) is None
    assert cp._parse_quando("qualquer coisa") is None
    assert isinstance(cp._parse_quando("2026-07-09 15:00"), float)


def test_chat_hermes_error_vira_502_sem_texto(spies, monkeypatch):
    secret = "conteudo-ultrassecreto-do-usuario"

    async def boom(prompt):
        raise RuntimeError("hermes_error")

    monkeypatch.setattr(settings, "hermes_mock", False)
    monkeypatch.setattr(cp.hermes_client, "_oneshot", boom)
    main.app.dependency_overrides[require_auth] = lambda: "test"

    with TestClient(main.app) as client:
        response = client.post(
            "/chat",
            json={"text": secret, "mode": "Mentor"},
        )

    assert response.status_code == 502
    assert response.json() == {"detail": "hermes_indisponivel"}
    assert secret not in response.text


def test_capture_client_key_idempotente_via_http(spies):
    main.app.dependency_overrides[require_auth] = lambda: "test"
    body = {
        "text": "captura cuja resposta pode se perder",
        "profile": "Capturas",
        "client_key": "phone-1720000000-abcd",
    }

    with TestClient(main.app) as client:
        first = client.post("/capture", json=body)
        second = client.post("/capture", json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json() == {
        "reply": "✅ anotado",
        "queued": True,
    }

    with store._connect() as con:
        rows = con.execute(
            "SELECT id, client_key FROM capture_queue WHERE client_key = ?",
            (body["client_key"],),
        ).fetchall()
    assert len(rows) == 1
