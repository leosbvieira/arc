from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import pontos, store, tasks
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "tasks_source", "mock")
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def _rotina(slug: str = "academia") -> dict:
    return {
        "id": 1,
        "slug": slug,
        "nome": "Academia",
        "bloco": "saúde",
        "dias": "*",
        "templates": "*",
        "passos": "",
        "ordem": 1,
        "origem": "manual",
    }


def test_objetivo_manual_acumula_e_exibe_12_semanas(client):
    resposta = client.post(
        "/objetivos",
        json={"nome": "  Academia  ", "alvo_semana": 3},
    )
    assert resposta.status_code == 200
    objetivo_id = resposta.json()["objetivo"]["id"]

    hoje = date.today()
    segunda = pontos.segunda_da_semana(hoje)
    primeira = segunda.isoformat()
    segunda_marca = (segunda + timedelta(days=1)).isoformat()

    primeira_resposta = client.post(
        f"/objetivos/{objetivo_id}/marcar",
        json={"data": primeira},
    )
    repetida = client.post(
        f"/objetivos/{objetivo_id}/marcar",
        json={"data": primeira},
    )
    terceira = client.post(
        f"/objetivos/{objetivo_id}/marcar",
        json={"data": segunda_marca},
    )

    assert primeira_resposta.json() == {"ok": True, "ja_estava": False}
    assert repetida.json() == {"ok": True, "ja_estava": True}
    assert terceira.json() == {"ok": True, "ja_estava": False}

    item = client.get("/objetivos").json()["objetivos"][0]
    progresso = item["progresso"]

    assert item["nome"] == "Academia"
    assert progresso["total"] == 2
    assert progresso["semana_atual"] == {
        "n": 2,
        "alvo": 3,
        "pct": 67,
    }
    assert len(progresso["serie"]) == 12
    assert progresso["serie"][-1]["n"] == 2
    assert any(ponto["n"] == 0 for ponto in progresso["serie"][:-1])


def test_objetivo_ligado_a_rotina_conta_so_feito(client, monkeypatch):
    monkeypatch.setattr(
        store,
        "list_routines",
        lambda incluir_inativas=False: [_rotina()],
    )

    resposta = client.post(
        "/objetivos",
        json={
            "nome": "Rotina de academia",
            "rotina_slug": "academia",
            "alvo_semana": 3,
        },
    )
    assert resposta.status_code == 200
    objetivo_id = resposta.json()["objetivo"]["id"]

    segunda = pontos.segunda_da_semana(date.today())
    store.record_checks(segunda.isoformat(), "yoga", [("academia", True)])
    store.record_checks((segunda + timedelta(days=1)).isoformat(), "yoga", [("academia", False)])
    store.record_checks((segunda + timedelta(days=2)).isoformat(), "yoga", [("academia", True)])

    item = client.get("/objetivos").json()["objetivos"][0]
    assert item["progresso"]["total"] == 2
    assert item["progresso"]["semana_atual"]["n"] == 2

    marcar = client.post(
        f"/objetivos/{objetivo_id}/marcar",
        json={"data": segunda.isoformat()},
    )
    assert marcar.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"nome": "Fantasma", "rotina_slug": "nao-existe"},
        {"nome": "Alvo zero", "alvo_semana": 0},
        {"nome": "Alvo oito", "alvo_semana": 8},
    ],
)
def test_post_objetivo_rejeita_fonte_ou_alvo_invalidos(client, payload):
    resposta = client.post("/objetivos", json=payload)
    assert resposta.status_code == 422


def test_delete_objetivo_e_soft_e_preserva_marcas(client):
    criado = client.post(
        "/objetivos",
        json={"nome": "Leitura"},
    ).json()["objetivo"]
    objetivo_id = criado["id"]

    client.post(
        f"/objetivos/{objetivo_id}/marcar",
        json={"data": "2026-07-10"},
    )

    resposta = client.delete(f"/objetivos/{objetivo_id}")
    assert resposta.status_code == 200
    assert resposta.json() == {"ok": True}
    assert client.get("/objetivos").json()["objetivos"] == []
    assert store.marcas_do_objetivo(objetivo_id) == ["2026-07-10"]


def test_is_primeiro_domingo():
    assert tasks.is_primeiro_domingo(date(2026, 8, 2)) is True
    assert tasks.is_primeiro_domingo(date(2026, 8, 9)) is False
    assert tasks.is_primeiro_domingo(date(2026, 7, 12)) is False


def test_monthly_review_pack_limita_tudo_ao_mes_anterior(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        store,
        "list_routines",
        lambda incluir_inativas=False: [_rotina()],
    )
    monkeypatch.setattr(settings, "pontos_por_rotina", 1)
    monkeypatch.setattr(settings, "desconto_padrao", 3)
    monkeypatch.setattr(settings, "teto_desconto_semanal", 10)
    monkeypatch.setattr(settings, "routine_miss_threshold", 3)

    ligado = store.create_objetivo(
        "Academia",
        rotina_slug="academia",
        alvo_semana=3,
    )
    manual = store.create_objetivo("Alongamento")

    store.marcar_objetivo(manual["id"], "2026-07-03")
    store.marcar_objetivo(manual["id"], "2026-07-20")
    store.marcar_objetivo(manual["id"], "2026-08-01")

    store.record_checks("2026-07-06", "yoga", [("academia", True)])
    store.record_checks("2026-07-07", "yoga", [("academia", False)])
    store.record_checks("2026-07-08", "yoga", [("academia", False)])
    store.record_checks("2026-07-09", "yoga", [("academia", False)])
    store.record_checks("2026-08-03", "yoga", [("academia", True)])

    fuso = ZoneInfo("America/Sao_Paulo")

    def ts(data_iso: str) -> float:
        return datetime.combine(
            date.fromisoformat(data_iso),
            time.min,
            tzinfo=fuso,
        ).timestamp()

    eventos = [
        ("closing_approved", "daily-1", ts("2026-07-02")),
        ("closing_approved", "daily-2", ts("2026-07-03")),
        ("closing_approved", "daily-3", ts("2026-08-01")),
        ("capture_done", "capture-1", ts("2026-07-04")),
        ("capture_done", "capture-2", ts("2026-08-01")),
    ]
    sessoes = [
        {
            "tipo": "leitura",
            "inicio": ts("2026-07-05"),
            "duracao_s": 600,
        },
        {
            "tipo": "leitura",
            "inicio": ts("2026-07-18"),
            "duracao_s": 1200,
        },
        {
            "tipo": "leitura",
            "inicio": ts("2026-08-01"),
            "duracao_s": 3600,
        },
    ]

    def contar(evento: str, desde: float, until_ts=None) -> int:
        refs = {
            ref
            for nome, ref, instante in eventos
            if nome == evento
            and instante >= desde
            and (until_ts is None or instante < until_ts)
        }
        return len(refs)

    def listar_sessoes(desde: float, until_ts=None) -> list[dict]:
        return [
            sessao
            for sessao in sessoes
            if sessao["inicio"] >= desde
            and (until_ts is None or sessao["inicio"] < until_ts)
        ]

    monkeypatch.setattr(store, "count_events_since", contar)
    monkeypatch.setattr(store, "list_sessions_since", listar_sessoes)

    pack = tasks.monthly_review_pack("2026-08-02")

    assert pack["mes"] == "2026-07"
    assert pack["scorecard"]["pct"] == 25
    assert pack["dailies"] == 2
    assert pack["capturas"] == 1
    assert pack["sessoes_leitura"] == {"n": 2, "min_total": 30}
    assert pack["pontos"] == {
        "ganho": 1,
        "desconto": 3,
        "saldo": 0,
    }
    assert pack["objetivos"] == [
        {"nome": ligado["nome"], "total_no_mes": 1},
        {"nome": manual["nome"], "total_no_mes": 2},
    ]

    texto = tasks.monthly_review_text("2026-08-02")
    assert "mês 2026-07" in texto
    assert "🏦 patrimônio" in texto


def test_nudge_funde_bloco_mensal_so_no_primeiro_domingo(
    client,
    monkeypatch,
):
    enviados: list[str] = []

    async def notificar(_chave: str, texto: str) -> dict:
        enviados.append(texto)
        return {"canal": "teste"}

    monkeypatch.setattr(store, "notif_sent_today", lambda _chave: False)
    monkeypatch.setattr(tasks, "weekly_review_text", lambda: "BLOCO SEMANAL")
    monkeypatch.setattr(tasks, "monthly_review_text", lambda: "BLOCO MENSAL")
    monkeypatch.setattr("app.main.notify.notificar", notificar)

    monkeypatch.setattr(tasks, "is_primeiro_domingo", lambda _ref: True)
    primeira = client.post(
        "/internal/nudge",
        json={"kind": "review"},
        headers={"X-Internal-Token": settings.internal_token},
    )
    assert primeira.status_code == 200
    assert "BLOCO SEMANAL" in enviados[-1]
    assert "BLOCO MENSAL" in enviados[-1]

    monkeypatch.setattr(tasks, "is_primeiro_domingo", lambda _ref: False)
    comum = client.post(
        "/internal/nudge",
        json={"kind": "review"},
        headers={"X-Internal-Token": settings.internal_token},
    )
    assert comum.status_code == 200
    assert "BLOCO SEMANAL" in enviados[-1]
    assert "BLOCO MENSAL" not in enviados[-1]


def test_resumo_periodo_considera_a_segunda_da_semana(
    client,
    monkeypatch,
):
    monkeypatch.setattr(settings, "pontos_por_rotina", 1)
    monkeypatch.setattr(settings, "desconto_padrao", 3)
    monkeypatch.setattr(settings, "teto_desconto_semanal", 10)
    monkeypatch.setattr(settings, "routine_miss_threshold", 3)

    store.record_checks("2026-06-29", "yoga", [("academia", True)])
    store.record_checks("2026-07-06", "yoga", [("academia", True)])
    store.record_checks("2026-07-13", "yoga", [("academia", False)])
    store.record_checks("2026-07-14", "yoga", [("academia", False)])
    store.record_checks("2026-07-15", "yoga", [("academia", False)])
    store.record_checks("2026-08-03", "yoga", [("academia", True)])

    assert pontos.resumo_periodo(
        date(2026, 7, 1),
        date(2026, 7, 31),
    ) == {
        "ganho": 1,
        "desconto": 3,
        "saldo": 0,
    }
