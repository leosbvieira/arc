"""O dia: toque das 5h30 (A1a) + check-in das 8h20 (A1b) — P2 item 6.

O buraco que isto fecha: o template de dia ("dia yoga / dia corrida") existia em
código, mas só aparecia na tela de FECHAMENTO das 21h — ou seja, o Leo marcava
"acordar 5h30" à noite, retroativamente. Agora:

- `POST /dia/template` é o toque das 5h30 (ele responde qual é o dia);
- `GET /abertura` é o pack da manhã (rotinas do bloco manhã + prioridades de ontem);
- `POST /routines/check` marca UMA rotina a qualquer hora — é isto que quebra o
  "marcar 5h30 às 21h";
- e o fechamento das 21h NÃO pode apagar o que já foi marcado de manhã (o teste
  mais importante do arquivo).
"""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import main, store
from app.config import settings
from app.main import app, require_auth

QUARTA = "2026-07-15"
HOJE = date.today().isoformat()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "tasks_source", "mock")
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def vault(monkeypatch):
    """Fechamento sem tocar o vault real."""
    async def fake_append(path, block, message, header_if_new="", dedupe_marker=None):
        return path

    async def fake_raw(text, capture_id, ts=None):
        return "1- Inbox/Raw/raw-x.md"

    monkeypatch.setattr(main.vault_client, "append_file", fake_append)
    monkeypatch.setattr(main.vault_client, "write_raw", fake_raw)


def _abertura(client, data=None) -> dict:
    r = client.get("/abertura", params={"data": data} if data else None)
    assert r.status_code == 200
    return r.json()


def _checks() -> dict[str, int]:
    return {
        row["rotina"]: row["feito"]
        for row in store.get_checks_since("2000-01-01")
    }


# --- POST /dia/template (o toque das 5h30) -----------------------------------


def test_template_grava_e_e_idempotente(client):
    for _ in range(3):
        r = client.post("/dia/template", json={"template": "corrida", "data": QUARTA})
        assert r.status_code == 200

    assert _abertura(client, QUARTA)["template"] == "corrida"
    assert store.get_dia(QUARTA)["template"] == "corrida"


def test_template_pode_ser_trocado_no_mesmo_dia(client):
    client.post("/dia/template", json={"template": "yoga", "data": QUARTA})
    client.post("/dia/template", json={"template": "corrida", "data": QUARTA})
    assert _abertura(client, QUARTA)["template"] == "corrida"


def test_template_invalido_e_422(client):
    r = client.post("/dia/template", json={"template": "natacao", "data": QUARTA})
    assert r.status_code == 422


def test_data_invalida_e_422(client):
    r = client.post("/dia/template", json={"template": "yoga", "data": "15/07/2026"})
    assert r.status_code == 422


def test_template_sem_data_e_hoje(client):
    client.post("/dia/template", json={"template": "yoga"})
    assert store.get_dia(HOJE)["template"] == "yoga"


# --- GET /abertura -----------------------------------------------------------


def test_abertura_sem_toque_ainda_traz_template_null(client):
    pack = _abertura(client, QUARTA)
    assert pack["data"] == QUARTA
    assert pack["template"] is None
    assert pack["checkin"] == {
        "feito": False, "energia": None, "clareza": None, "prioridade_1": None,
    }
    assert pack["prioridades_de_ontem"] == []


def test_abertura_sem_template_so_traz_rotina_de_qualquer_template(client):
    """Sem o toque, o sistema NÃO sabe se é dia yoga ou corrida — então não inventa:
    mostra só o que vale nos dois. yoga/meditação/corrida aparecem depois da escolha."""
    slugs = [r["slug"] for r in _abertura(client, QUARTA)["rotinas_manha"]]
    assert "acordar-5h30" in slugs and "academia" in slugs
    assert "yoga" not in slugs and "corrida" not in slugs and "meditacao" not in slugs


def test_abertura_so_traz_o_bloco_manha_e_o_do_dia(client):
    client.post("/dia/template", json={"template": "yoga", "data": QUARTA})
    slugs = [r["slug"] for r in _abertura(client, QUARTA)["rotinas_manha"]]

    assert "acordar-5h30" in slugs and "yoga" in slugs
    assert "mascara" not in slugs          # quarta, mas é NOITE
    assert "diario" not in slugs           # noite
    assert "arrumar-casa" not in slugs     # bloco 'dia', e domingo


def test_abertura_respeita_o_template_do_toque(client):
    client.post("/dia/template", json={"template": "corrida", "data": QUARTA})
    slugs = [r["slug"] for r in _abertura(client, QUARTA)["rotinas_manha"]]
    assert "corrida" in slugs and "yoga" not in slugs
    assert slugs.index("academia") < slugs.index("corrida")   # a corrida vem depois


def test_abertura_traz_passos_e_feito(client):
    client.post("/dia/template", json={"template": "yoga", "data": QUARTA})
    client.post("/routines/check", json={"slug": "pesagem", "feito": True, "data": QUARTA})

    rotinas = {r["slug"]: r for r in _abertura(client, QUARTA)["rotinas_manha"]}
    assert rotinas["pesagem"]["feito"] is True
    assert rotinas["acordar-5h30"]["feito"] is False
    assert rotinas["skincare"]["passos"] == ["limpeza", "hidratante", "protetor solar"]
    assert set(rotinas["pesagem"]) == {"id", "slug", "nome", "passos", "feito"}


def test_abertura_traz_horarios_do_dia(client):
    from datetime import datetime, time
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Sao_Paulo")
    quando = datetime.combine(date.fromisoformat(QUARTA), time(15, 0), tzinfo=tz)
    store.add_schedule(quando.timestamp(), "cobrar-terceiro", "cobrar o Yan")
    store.add_schedule(
        (quando + timedelta(days=1)).timestamp(), "minha", "de amanhã, não entra",
    )

    assert _abertura(client, QUARTA)["hoje"]["horarios"] == [
        {"hora": "15:00", "ref": "cobrar o Yan"},
    ]


def test_abertura_traz_tarefas_vencendo_hoje(client):
    hoje = _abertura(client)["hoje"]
    nomes = [t["name"] for t in hoje["tarefas_due"]]
    assert "Relatório mensal" in nomes        # due hoje (mock)
    assert "Pagar fatura do cartão" in nomes  # atrasada 2d — continua sendo coisa de hoje
    assert "Dentista" not in nomes            # sem due


def test_abertura_exige_auth():
    app.dependency_overrides.clear()
    assert TestClient(app).get("/abertura").status_code == 401


# --- POST /abertura/checkin (8h20) -------------------------------------------


def test_checkin_grava_e_aparece_na_abertura(client):
    client.post("/dia/template", json={"template": "yoga", "data": QUARTA})
    r = client.post(
        "/abertura/checkin",
        json={
            "energia": "alta",
            "clareza": "media",
            "prioridade_1": "fechar a proposta do Yan",
            "data": QUARTA,
        },
    )
    assert r.status_code == 200

    pack = _abertura(client, QUARTA)
    assert pack["checkin"] == {
        "feito": True,
        "energia": "alta",
        "clareza": "media",
        "prioridade_1": "fechar a proposta do Yan",
    }
    assert pack["template"] == "yoga"          # o check-in NÃO apaga o toque


def test_checkin_antes_do_toque_nao_perde_o_template_depois(client):
    client.post(
        "/abertura/checkin",
        json={"energia": "baixa", "clareza": "baixa", "prioridade_1": "x", "data": QUARTA},
    )
    client.post("/dia/template", json={"template": "corrida", "data": QUARTA})

    pack = _abertura(client, QUARTA)
    assert pack["template"] == "corrida"
    assert pack["checkin"]["feito"] is True    # o toque NÃO apaga o check-in


def test_checkin_energia_invalida_e_422(client):
    r = client.post(
        "/abertura/checkin",
        json={"energia": "turbo", "clareza": "alta", "prioridade_1": "x"},
    )
    assert r.status_code == 422


# --- POST /routines/check (marcar a QUALQUER hora) ---------------------------


def test_check_marca_uma_rotina_isolada(client):
    r = client.post("/routines/check", json={"slug": "acordar-5h30", "feito": True})
    assert r.status_code == 200
    assert _checks() == {"acordar-5h30": 1}


def test_check_e_idempotente_e_reversivel(client):
    client.post("/routines/check", json={"slug": "acordar-5h30", "feito": True})
    client.post("/routines/check", json={"slug": "acordar-5h30", "feito": True})
    assert _checks() == {"acordar-5h30": 1}

    client.post("/routines/check", json={"slug": "acordar-5h30", "feito": False})
    assert _checks() == {"acordar-5h30": 0}


def test_check_usa_o_template_do_dia(client):
    client.post("/dia/template", json={"template": "corrida", "data": QUARTA})
    client.post("/routines/check", json={"slug": "corrida", "feito": True, "data": QUARTA})

    rows = store.get_checks_since("2000-01-01")
    assert [(r["rotina"], r["template"]) for r in rows] == [("corrida", "corrida")]


def test_check_sem_template_escolhido_cai_em_yoga(client):
    """Documentado: sem o toque das 5h30, o check grava com o template default 'yoga'."""
    client.post("/routines/check", json={"slug": "pesagem", "feito": True, "data": QUARTA})
    rows = store.get_checks_since("2000-01-01")
    assert rows[0]["template"] == "yoga"


def test_check_de_slug_inexistente_e_404(client):
    r = client.post("/routines/check", json={"slug": "nao-existe", "feito": True})
    assert r.status_code == 404
    assert _checks() == {}          # e não sujou o histórico


def test_check_exige_auth():
    app.dependency_overrides.clear()
    r = TestClient(app).post("/routines/check", json={"slug": "pesagem", "feito": True})
    assert r.status_code == 401


# --- O TESTE: a marcação da manhã SOBREVIVE ao fechamento das 21h ------------


def test_marcado_de_manha_sobrevive_ao_fechamento_da_noite(client, vault):
    """O bug de origem: ele marcava 'acordar 5h30' às 21h, retroativamente. Agora ele
    marca de manhã — e o fechamento das 21h, que grava com INSERT OR REPLACE, NÃO pode
    apagar o que já estava lá (só reescreve as linhas que o app mandar)."""
    client.post("/dia/template", json={"template": "yoga"})
    client.post("/routines/check", json={"slug": "acordar-5h30", "feito": True})
    client.post("/routines/check", json={"slug": "pesagem", "feito": True})

    # o fechamento manda só o que a tela das 21h mostra (a noite)
    r = client.post("/closing/approve", json={
        "raw_text": "dia ok",
        "draft_md": "## Diário",
        "template": "yoga",
        "checks": [
            {"rotina": "diario", "feito": True},
            {"rotina": "leitura-noturna", "feito": False},
        ],
    })
    assert r.status_code == 200

    assert _checks() == {
        "acordar-5h30": 1,      # SOBREVIVEU
        "pesagem": 1,           # SOBREVIVEU
        "diario": 1,
        "leitura-noturna": 0,
    }


def test_fechamento_com_o_dia_inteiro_preserva_a_manha(client, vault):
    """E quando o app manda o estado COMPLETO do dia (o caminho normal), o que foi
    marcado de manhã continua marcado — o REPLACE reescreve o mesmo valor."""
    client.post("/routines/check", json={"slug": "acordar-5h30", "feito": True})

    client.post("/closing/approve", json={
        "raw_text": "x", "draft_md": "y", "template": "yoga",
        "checks": [
            {"rotina": "acordar-5h30", "feito": True},
            {"rotina": "diario", "feito": True},
        ],
    })

    assert _checks()["acordar-5h30"] == 1


def test_fechamento_pode_corrigir_a_marcacao_da_manha(client, vault):
    """O inverso também vale: se ele marcou errado de manhã, a tela das 21h corrige."""
    client.post("/routines/check", json={"slug": "acordar-5h30", "feito": True})

    client.post("/closing/approve", json={
        "raw_text": "x", "draft_md": "y", "template": "yoga",
        "checks": [{"rotina": "acordar-5h30", "feito": False}],
    })

    assert _checks()["acordar-5h30"] == 0
