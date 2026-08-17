"""Rotinas como DADO editável (P2 item 2).

Antes: `routines.ROUTINES` — dict hardcoded, 6 strings por template. Agora: tabela
`routines` (slug estável, bloco, dias da semana, templates, passos ordenados), semeada
com exemplos e editável pelo app.

Invariantes que estes testes travam:
- o `slug` é a chave do histórico: nasce uma vez e NUNCA muda (renomear é seguro);
- DELETE é soft (`ativo=0`) — o scorecard das semanas passadas não pode evaporar;
- `passos` são roteiro, NÃO checks: não contam no scorecard nem viram linha em
  `routine_checks` (decisão do Leo, 12/jul);
- no dia corrida, a corrida vem SEMPRE depois da academia (garantido por `ordem`).
"""
import pytest
from fastapi.testclient import TestClient

from app import main, store
from app.config import settings
from app.main import app, require_auth

QUARTA = "2026-07-15"
TERCA = "2026-07-14"
DOMINGO = "2026-07-19"
SEGUNDA = "2026-07-13"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def _slugs(payload: dict) -> list[str]:
    return [r["slug"] for r in payload["routines"]]


def _fechamento(client, *, template="yoga", date=QUARTA) -> dict:
    r = client.get("/closing/routines", params={"template": template, "date": date})
    assert r.status_code == 200
    return r.json()


# --- semente ----------------------------------------------------------------


def test_semente_idempotente(client):
    """init_db roda em todo boot; semear duas vezes não pode duplicar."""
    antes = _slugs(client.get("/routines").json())
    store.init_db()
    store.init_db()
    depois = _slugs(client.get("/routines").json())
    assert antes == depois
    assert len(depois) == 12
    assert depois.count("skincare") == 1


def test_semente_preserva_os_slugs_historicos(client):
    """Os 6 checks que já existem em routine_checks continuam apontando pra rotina certa."""
    slugs = set(_slugs(client.get("/routines").json()))
    antigos = {
        "acordar-5h30", "yoga", "meditacao", "skincare", "academia",
        "leitura-noturna", "corrida",
    }
    assert antigos <= slugs


def test_semente_marca_origem_exemplo(client):
    rotinas = client.get("/routines").json()["routines"]
    assert {r["origem"] for r in rotinas} == {"exemplo"}


def test_semente_traz_passos_ordenados_do_skincare(client):
    rotinas = {r["slug"]: r for r in client.get("/routines").json()["routines"]}
    assert rotinas["skincare"]["passos"] == ["limpeza", "hidratante", "protetor solar"]
    assert rotinas["skincare-pm"]["passos"] == ["limpeza", "sérum", "hidratante"]
    assert rotinas["pesagem"]["passos"] == []


# --- GET /routines ----------------------------------------------------------


def test_get_routines_ordena_manha_dia_noite(client):
    blocos = [r["bloco"] for r in client.get("/routines").json()["routines"]]
    assert blocos == sorted(blocos, key=lambda b: ["manha", "dia", "noite"].index(b))
    assert blocos[0] == "manha" and blocos[-1] == "noite"
    assert "dia" in blocos


def test_get_routines_exige_auth():
    app.dependency_overrides.clear()
    r = TestClient(app).get("/routines")
    assert r.status_code == 401


# --- CRUD -------------------------------------------------------------------


def test_post_cria_com_origem_leo_e_slug_do_nome(client):
    r = client.post("/routines", json={"nome": "Alongamento Lombar", "bloco": "noite"})
    assert r.status_code == 200
    nova = r.json()
    assert nova["slug"] == "alongamento-lombar"
    assert nova["origem"] == "leo"
    assert nova["dias"] == "*" and nova["templates"] == "*" and nova["passos"] == []
    assert nova["id"] > 0
    assert "alongamento-lombar" in _slugs(client.get("/routines").json())


def test_post_slug_unico_sufixa_na_colisao(client):
    a = client.post("/routines", json={"nome": "skincare", "bloco": "manha"}).json()
    b = client.post("/routines", json={"nome": "Skincare", "bloco": "noite"}).json()
    assert a["slug"] == "skincare-2"   # 'skincare' já é da semente
    assert b["slug"] == "skincare-3"


def test_post_ordem_e_max_mais_um_do_bloco(client):
    noite = [r for r in client.get("/routines").json()["routines"] if r["bloco"] == "noite"]
    maior = max(r["ordem"] for r in noite)
    nova = client.post("/routines", json={"nome": "chá", "bloco": "noite"}).json()
    assert nova["ordem"] == maior + 1


def test_post_com_passos_e_dias(client):
    nova = client.post("/routines", json={
        "nome": "Barba", "bloco": "manha", "dias": "sab,dom",
        "templates": "*", "passos": ["espuma", "lâmina", "pós-barba"],
    }).json()
    assert nova["passos"] == ["espuma", "lâmina", "pós-barba"]
    assert nova["dias"] == "sab,dom"


def test_post_bloco_invalido_e_422(client):
    r = client.post("/routines", json={"nome": "x", "bloco": "madrugada"})
    assert r.status_code == 422


def test_post_dia_invalido_e_422(client):
    r = client.post("/routines", json={"nome": "x", "bloco": "manha", "dias": "wed"})
    assert r.status_code == 422


def test_patch_atualiza_mas_nunca_muda_o_slug(client):
    rotinas = {r["slug"]: r for r in client.get("/routines").json()["routines"]}
    rid = rotinas["skincare"]["id"]
    r = client.patch(f"/routines/{rid}", json={
        "nome": "skincare da manhã (novo)", "passos": ["limpeza", "vitamina C", "protetor"],
    })
    assert r.status_code == 200
    atualizada = r.json()
    assert atualizada["slug"] == "skincare"                 # histórico intacto
    assert atualizada["nome"] == "skincare da manhã (novo)"
    assert atualizada["passos"] == ["limpeza", "vitamina C", "protetor"]


def test_patch_ignora_slug_no_body(client):
    rid = client.post("/routines", json={"nome": "Ler news", "bloco": "manha"}).json()["id"]
    r = client.patch(f"/routines/{rid}", json={"slug": "hackeado", "nome": "Ler notícias"})
    assert r.status_code == 200
    assert r.json()["slug"] == "ler-news"


def test_patch_move_de_bloco(client):
    rid = client.post("/routines", json={"nome": "Água", "bloco": "manha"}).json()["id"]
    assert client.patch(f"/routines/{rid}", json={"bloco": "noite"}).json()["bloco"] == "noite"


def test_patch_inexistente_e_404(client):
    assert client.patch("/routines/9999", json={"nome": "x"}).status_code == 404


def test_delete_e_soft_e_preserva_o_historico(client):
    rotinas = {r["slug"]: r for r in client.get("/routines").json()["routines"]}
    rid = rotinas["mascara"]["id"]

    store.record_checks("2026-07-08", "yoga", [("mascara", True)])

    assert client.delete(f"/routines/{rid}").status_code == 200
    assert "mascara" not in _slugs(client.get("/routines").json())

    # o check antigo continua lá — o scorecard das semanas passadas não pode evaporar
    rows = store.get_checks_since("2000-01-01")
    assert ("mascara", 1) in {(x["rotina"], x["feito"]) for x in rows}


def test_delete_some_do_fechamento(client):
    rotinas = {r["slug"]: r for r in client.get("/routines").json()["routines"]}
    client.delete(f"/routines/{rotinas['pesagem']['id']}")
    assert "pesagem" not in _slugs(_fechamento(client))


def test_delete_inexistente_e_404(client):
    assert client.delete("/routines/9999").status_code == 404


def test_reorder_em_lote(client):
    rotinas = {r["slug"]: r for r in client.get("/routines").json()["routines"]}
    pesagem, acordar = rotinas["pesagem"], rotinas["acordar-5h30"]
    r = client.post("/routines/reorder", json={"ordem": [
        {"id": pesagem["id"], "ordem": acordar["ordem"]},
        {"id": acordar["id"], "ordem": pesagem["ordem"]},
    ]})
    assert r.status_code == 200
    depois = _slugs(client.get("/routines").json())
    assert depois.index("pesagem") < depois.index("acordar-5h30")


# --- filtro por dia da semana ------------------------------------------------


def test_quarta_tem_mascara_e_terca_nao(client):
    assert "mascara" in _slugs(_fechamento(client, date=QUARTA))
    assert "mascara" not in _slugs(_fechamento(client, date=TERCA))


def test_domingo_tem_arrumar_a_casa(client):
    assert "arrumar-casa" in _slugs(_fechamento(client, date=DOMINGO))
    assert "arrumar-casa" not in _slugs(_fechamento(client, date=SEGUNDA))


def test_rotina_de_todo_dia_aparece_sempre(client):
    for dia in (SEGUNDA, TERCA, QUARTA, DOMINGO):
        assert "diario" in _slugs(_fechamento(client, date=dia))


def test_date_default_e_hoje(client):
    from datetime import date as _date

    from app import routines as rt

    hoje = client.get("/closing/routines", params={"template": "yoga"}).json()
    explicito = _fechamento(client, date=_date.today().isoformat())
    assert _slugs(hoje) == _slugs(explicito)
    assert rt.dia_sigla(_date.fromisoformat(QUARTA)) == "qua"


# --- filtro por template ------------------------------------------------------


def test_dia_corrida_nao_traz_yoga_nem_meditacao(client):
    slugs = _slugs(_fechamento(client, template="corrida", date=QUARTA))
    assert "yoga" not in slugs and "meditacao" not in slugs
    assert "corrida" in slugs


def test_dia_yoga_traz_yoga_e_nao_traz_corrida(client):
    slugs = _slugs(_fechamento(client, template="yoga", date=QUARTA))
    assert "yoga" in slugs and "meditacao" in slugs
    assert "corrida" not in slugs


def test_academia_aparece_nos_dois_templates(client):
    for template in ("yoga", "corrida"):
        assert "academia" in _slugs(_fechamento(client, template=template, date=QUARTA))


def test_corrida_sempre_depois_da_academia(client):
    slugs = _slugs(_fechamento(client, template="corrida", date=QUARTA))
    assert slugs.index("academia") < slugs.index("corrida")


def test_fechamento_devolve_objetos_com_passos(client):
    rotinas = _fechamento(client)["routines"]
    skincare = next(r for r in rotinas if r["slug"] == "skincare")
    assert set(skincare) == {"id", "slug", "nome", "bloco", "passos", "feito"}
    assert skincare["nome"] == "skincare AM"
    assert skincare["bloco"] == "manha"
    assert skincare["passos"] == ["limpeza", "hidratante", "protetor solar"]


def test_fechamento_ordena_manha_antes_de_noite(client):
    blocos = [r["bloco"] for r in _fechamento(client, date=DOMINGO)["routines"]]
    assert blocos.index("manha") < blocos.index("noite")
    assert blocos.index("dia") < blocos.index("noite")   # arrumar a casa (dom)


# --- integração com o scorecard (o slug é a ponte) ---------------------------


def test_approve_grava_pelo_slug_e_o_scorecard_conta(client, monkeypatch):
    async def fake_append(path, block, message, header_if_new="", dedupe_marker=None, **_kw):
        return path

    async def fake_raw(text, capture_id, ts=None):
        return "1- Inbox/Raw/raw-x.md"

    monkeypatch.setattr(main.vault_client, "append_file", fake_append)
    monkeypatch.setattr(main.vault_client, "write_raw", fake_raw)

    rotinas = _fechamento(client, template="corrida", date=QUARTA)["routines"]
    checks = [{"rotina": r["slug"], "feito": r["slug"] != "corrida"} for r in rotinas]
    r = client.post("/closing/approve", json={
        "raw_text": "dia ok", "draft_md": "## Diário", "template": "corrida",
        "checks": checks,
    })
    assert r.status_code == 200

    # approve grava sob a data REAL de hoje — então o pack é o da semana corrente
    from app import tasks
    pack = tasks.weekly_review_pack()
    por_rotina = pack["scorecard"]["por_rotina"]
    assert set(por_rotina) == {c["rotina"] for c in checks}      # gravou pelo slug
    assert por_rotina["corrida"] == {"feitos": 0, "dias": 1}
    assert por_rotina["academia"] == {"feitos": 1, "dias": 1}
    assert 0 < pack["scorecard"]["pct"] < 100                    # scorecard não quebrou


def test_passos_nao_viram_checks(client, monkeypatch):
    async def fake_append(path, block, message, header_if_new="", dedupe_marker=None, **_kw):
        return path

    async def fake_raw(text, capture_id, ts=None):
        return "1- Inbox/Raw/raw-y.md"

    monkeypatch.setattr(main.vault_client, "append_file", fake_append)
    monkeypatch.setattr(main.vault_client, "write_raw", fake_raw)

    rotinas = _fechamento(client)["routines"]
    checks = [{"rotina": r["slug"], "feito": True} for r in rotinas]
    client.post("/closing/approve", json={
        "raw_text": "x", "draft_md": "y", "template": "yoga", "checks": checks,
    })

    gravados = {row["rotina"] for row in store.get_checks_since("2000-01-01")}
    assert "skincare" in gravados
    # nenhum passo ('limpeza', 'protetor solar', 'sérum'...) virou linha de check
    passos = {p for r in rotinas for p in r["passos"]}
    assert passos and not (passos & gravados)
    assert len(gravados) == len(rotinas)          # 1 check por item PAI, ponto
