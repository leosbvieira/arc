import base64, json
import httpx
import pytest
from app import vault_client as vc
from app.config import settings

@pytest.fixture(autouse=True)
def _cfg(monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "tok")
    monkeypatch.setattr(settings, "vault_repo", "leosbvieira/aeternum")

def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.github.com")

async def test_put_cria_quando_404(monkeypatch):
    calls = []
    def handler(req):
        calls.append(req.method)
        if req.method == "GET":
            return httpx.Response(404)
        assert base64.b64decode(json.loads(req.content)["content"]).decode() == "oi"
        return httpx.Response(201, json={"content": {"path": "Daily/2026-07-09.md"}})
    monkeypatch.setattr(vc, "_client", lambda: _client(handler))
    assert await vc.put_file("Daily/2026-07-09.md", "oi", "msg") == "Daily/2026-07-09.md"
    assert calls == ["GET", "PUT"]

async def test_conflito_de_sha_refaz_e_passa(monkeypatch):
    state = {"puts": 0}
    def handler(req):
        if req.method == "GET":
            sha = "v1" if state["puts"] == 0 else "v2"
            return httpx.Response(200, json={"sha": sha, "encoding": "base64",
                "content": base64.b64encode(b"# dia\n").decode()})
        state["puts"] += 1
        if json.loads(req.content)["sha"] == "v1":
            return httpx.Response(409)                     # outro escritor passou na frente
        return httpx.Response(200, json={"content": {"path": "Daily/x.md"}})
    monkeypatch.setattr(vc, "_client", lambda: _client(handler))
    await vc.append_file("Daily/x.md", "bloco\n", "msg")
    assert state["puts"] == 2                              # retry com sha novo

async def test_append_com_dedupe_marker_nao_duplica(monkeypatch):
    def handler(req):
        if req.method == "GET":
            return httpx.Response(200, json={"sha": "s", "encoding": "base64",
                "content": base64.b64encode("# dia\n<!-- fech:2026-07-09:abc -->\nja gravado\n".encode()).decode()})
        raise AssertionError("nao deveria dar PUT")
    monkeypatch.setattr(vc, "_client", lambda: _client(handler))
    path = await vc.append_file("Daily/x.md", "bloco", "msg", dedupe_marker="<!-- fech:2026-07-09:abc -->")
    assert path == "Daily/x.md"                            # idempotente: bloco ja existe

async def test_write_raw_verbatim_neutro_e_deterministico(monkeypatch):
    seen = {"puts": 0}
    exists = {"flag": False}
    def handler(req):
        if req.method == "GET":
            if exists["flag"]:
                return httpx.Response(200, json={"sha": "s", "encoding": "base64",
                    "content": base64.b64encode(b"x").decode()})
            return httpx.Response(404)
        seen["puts"] += 1
        body = json.loads(req.content)
        seen["path"] = req.url.path
        seen["text"] = base64.b64decode(body["content"]).decode()
        seen["msg"] = body["message"]
        exists["flag"] = True
        return httpx.Response(201, json={"content": {"path": "x"}})
    monkeypatch.setattr(vc, "_client", lambda: _client(handler))
    texto = "terapia: crise forte hoje — detalhe sensivel"
    ts_origem = 1751980000.0                                # ts do enfileiramento (fixo entre retries)
    p1 = await vc.write_raw(texto, 42, ts=ts_origem)
    p2 = await vc.write_raw(texto, 42, ts=ts_origem)        # retry horas depois: mesmo ts de origem
    assert p1 == p2 and seen["puts"] == 1                   # deterministico: UM arquivo, sem duplicar
    assert seen["text"] == texto                            # verbatim byte a byte
    assert "raw-c42" in seen["path"] and "terapia" not in seen["path"]   # path neutro (lei 7)
    assert "terapia" not in seen["msg"] and seen["msg"] == "raw: c42"    # commit neutro


async def test_reading_path_idempotente_e_resiste_reset_de_ids(monkeypatch):
    existentes = set()
    puts = []

    async def fake_get(path):
        return {"sha": "s"} if path in existentes else None

    async def fake_put(path, content, message):
        puts.append((path, content, message))
        existentes.add(path)
        return path

    monkeypatch.setattr(vc, "_get", fake_get)
    monkeypatch.setattr(vc, "put_file", fake_put)

    kwargs = {"ts": 1_751_980_000.0, "client_key": "device-session-A"}
    first = await vc.write_reading_note("# Nota", 1, **kwargs)
    retry = await vc.write_reading_note("# Nota", 1, **kwargs)
    other_db_same_id = await vc.write_reading_note(
        "# Outra",
        1,
        ts=kwargs["ts"],
        client_key="device-session-B",
    )

    assert first == retry
    assert first != other_db_same_id
    assert len(puts) == 2
    assert all("device-session" not in path for path, _, _ in puts)
    assert all(message == "leitura: r1" for _, _, message in puts)

async def test_erro_vira_vault_error(monkeypatch):
    def handler(req):
        return httpx.Response(500)
    monkeypatch.setattr(vc, "_client", lambda: _client(handler))
    with pytest.raises(vc.VaultError):
        await vc.put_file("x.md", "y", "m")


async def test_sem_pat_falha_nomeada(monkeypatch):
    monkeypatch.setattr(settings, "github_pat", "")
    with pytest.raises(vc.VaultError, match="vault_nao_configurado"):
        await vc.write_raw("qualquer", 1)
