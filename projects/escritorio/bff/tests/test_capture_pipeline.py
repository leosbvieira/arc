import pytest
from app import capture_pipeline as cp
from app import store
from app.config import settings

@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()

@pytest.fixture
def spies(monkeypatch):
    calls = {"raw": [], "clickup": [], "classify": []}
    async def fake_raw(text, capture_id, ts=None):
        calls["raw"].append((text, capture_id)); return f"1- Inbox/Raw/raw-c{capture_id}.md"
    async def fake_classify(text):
        calls["classify"].append(text)
        return {"tipo": "nota", "titulo": None, "quando": None}
    async def fake_create(area, nome, due_ts=None, tags=None, description=None):
        calls["clickup"].append({"area": area, "nome": nome, "due": due_ts, "tags": tags, "desc": description})
        return {"id": "tsk1", "name": nome}
    monkeypatch.setattr(cp.vault_client, "write_raw", fake_raw)
    monkeypatch.setattr(cp.hermes_client, "classify", fake_classify)
    monkeypatch.setattr(cp, "_create_task", fake_create)
    return calls

async def test_nota_vira_so_raw(spies):
    store.enqueue_capture("pensamento solto sobre estoicismo", None)
    assert await cp.process_pending() == 1
    assert spies["raw"][0][0] == "pensamento solto sobre estoicismo"
    assert spies["clickup"] == [] and store.pending_captures() == []

async def test_toda_tarefa_vai_pra_staging_com_link_do_raw(spies, monkeypatch):
    async def classify(text):
        return {"tipo": "tarefa_pessoal", "titulo": "Comprar presente", "quando": None}
    monkeypatch.setattr(cp.hermes_client, "classify", classify)
    cid = store.enqueue_capture("comprar presente pra mae", None)
    await cp.process_pending()
    call = spies["clickup"][0]
    assert call["area"] == "Staging"                      # destino final e do Leo (B6/lei 3)
    assert f"raw-c{cid}" in call["desc"]                  # link de volta ao Raw (raw-first §8)
    assert f"[cap:{cid}]" in call["desc"]                 # marker de idempotencia

async def test_cobranca_leva_tag_aguardando_e_schedule(spies, monkeypatch):
    async def classify(text):
        return {"tipo": "cobranca", "titulo": "Cobrar Yan do contrato", "quando": "2026-07-09 15:00"}
    monkeypatch.setattr(cp.hermes_client, "classify", classify)
    store.enqueue_capture("cobrar o Yan do contrato as 15h", None)
    await cp.process_pending()
    call = spies["clickup"][0]
    assert call["tags"] == ["aguardando"] and call["due"] is not None
    assert len(store.due_schedules(call["due"] + 1)) == 1  # lembrete generico agendado

async def test_hermes_caido_preserva_raw_e_retenta(spies, monkeypatch):
    async def boom(text):
        raise RuntimeError("timeout")
    monkeypatch.setattr(cp.hermes_client, "classify", boom)
    store.enqueue_capture("nada se perde", None)
    await cp.process_pending()
    row = store.pending_captures()[0]
    assert row["raw_path"] and row["attempts"] == 1
    assert "nada se perde" not in (row["last_error"] or "")   # erro sanitizado (lei 7)
    await cp.process_pending()
    assert len(spies["raw"]) == 1                              # raw nao regrava (idempotencia)

async def test_classify_invalido_degrada_para_nota(spies, monkeypatch):
    async def classify(text):
        return {"tipo": "alucinado", "titulo": None, "quando": None}
    monkeypatch.setattr(cp.hermes_client, "classify", classify)
    store.enqueue_capture("qualquer coisa", None)
    await cp.process_pending()
    assert spies["clickup"] == [] and store.pending_captures() == []

async def test_ja_criado_no_clickup_nao_duplica(spies, monkeypatch):
    async def classify(text):
        return {"tipo": "tarefa_pessoal", "titulo": "X", "quando": None}
    monkeypatch.setattr(cp.hermes_client, "classify", classify)
    cid = store.enqueue_capture("x", None)
    store.mark_capture(cid, raw_path="r.md", clickup_task_id="tsk9")   # crash simulado pos-create
    await cp.process_pending()
    assert spies["clickup"] == []                                       # nao recria

def test_parse_quando_degrada_para_none_em_lixo():
    assert cp._parse_quando(None) is None                              # sem quando
    assert cp._parse_quando(123) is None                              # nao-string de modelo malcomportado (TypeError)
    assert cp._parse_quando("qualquer coisa") is None                 # formato invalido (ValueError)
    assert isinstance(cp._parse_quando("2026-07-09 15:00"), float)     # hora marcada vira epoch
