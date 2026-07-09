import pytest
from fastapi.testclient import TestClient
from app import main, store
from app.config import settings
from app.main import app, require_auth

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_draft_devolve_estrutura(client, monkeypatch):
    async def fake_draft(text, template):
        return f"## Diario\n{text}"
    monkeypatch.setattr(main.hermes_client, "draft_diario", fake_draft)
    r = client.post("/closing/draft", json={"text": "dia bom, treinei", "template": "yoga"})
    assert r.status_code == 200 and r.json()["draft"].startswith("## Diario")

def test_approve_grava_exatamente_o_aprovado_com_link_e_marker(client, monkeypatch):
    written = {}
    async def fake_append(path, block, message, header_if_new="", dedupe_marker=None):
        written.update(path=path, block=block, marker=dedupe_marker)
        return path
    async def fake_raw(text, capture_id):
        written["raw"] = text
        return "1- Inbox/Raw/raw-cf1.md"
    monkeypatch.setattr(main.vault_client, "append_file", fake_append)
    monkeypatch.setattr(main.vault_client, "write_raw", fake_raw)
    body = {"raw_text": "dia bom, treinei", "draft_md": "## Diario\nEDITADO PELO LEO",
            "template": "yoga", "checks": [{"rotina": "yoga", "feito": True}, {"rotina": "academia", "feito": False}]}
    r = client.post("/closing/approve", json=body)
    assert r.status_code == 200
    assert "EDITADO PELO LEO" in written["block"]           # o que aprova e o que grava
    assert written["raw"] == "dia bom, treinei"             # raw verbatim
    assert "raw-cf1" in written["block"]                    # link de volta ao Raw (§8 raw-first)
    assert written["marker"] and written["marker"] in written["block"]   # dedupe de retry
    rows = store.get_checks_since("2000-01-01")
    assert {(x["rotina"], x["feito"]) for x in rows} == {("yoga", 1), ("academia", 0)}

def test_routines_por_template(client):
    r = client.get("/closing/routines", params={"template": "corrida"})
    assert "corrida" in r.json()["routines"] and "yoga" not in r.json()["routines"]
