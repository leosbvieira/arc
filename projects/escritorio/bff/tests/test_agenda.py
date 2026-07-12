from datetime import date, datetime, time as _time, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import agenda, ics_client, store, tasks
from app.config import settings
from app.main import app, require_auth

TZ = ZoneInfo("America/Sao_Paulo")


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "tasks_source", "mock")
    monkeypatch.setattr(settings, "gcal_ics_url", "")
    monkeypatch.setattr(settings, "outlook_ics_url", "")
    monkeypatch.setattr(settings, "ics_cache_ttl", 900)
    store.init_db()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "tasks_source", "mock")
    monkeypatch.setattr(settings, "gcal_ics_url", "")
    monkeypatch.setattr(settings, "outlook_ics_url", "")
    monkeypatch.setattr(settings, "ics_cache_ttl", 900)
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def _ics(ref: date) -> str:
    anterior = ref - timedelta(days=7)
    outro = ref + timedelta(days=1)
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Aeternum Tests//PT-BR",
            "CALSCALE:GREGORIAN",
            "BEGIN:VEVENT",
            "UID:com-hora",
            "DTSTAMP:20260101T000000Z",
            f"DTSTART;TZID=America/Sao_Paulo:{ref:%Y%m%d}T093000",
            f"DTEND;TZID=America/Sao_Paulo:{ref:%Y%m%d}T103000",
            "SUMMARY:Reunião ITER",
            "END:VEVENT",
            "BEGIN:VEVENT",
            "UID:dia-inteiro",
            "DTSTAMP:20260101T000000Z",
            f"DTSTART;VALUE=DATE:{ref:%Y%m%d}",
            f"DTEND;VALUE=DATE:{(ref + timedelta(days=1)):%Y%m%d}",
            "SUMMARY:Aniversário",
            "END:VEVENT",
            "BEGIN:VEVENT",
            "UID:recorrente",
            "DTSTAMP:20260101T000000Z",
            f"DTSTART;TZID=America/Sao_Paulo:{anterior:%Y%m%d}T110000",
            f"DTEND;TZID=America/Sao_Paulo:{anterior:%Y%m%d}T113000",
            "RRULE:FREQ=WEEKLY",
            "SUMMARY:Reunião semanal",
            "END:VEVENT",
            "BEGIN:VEVENT",
            "UID:outro-dia",
            "DTSTAMP:20260101T000000Z",
            f"DTSTART;TZID=America/Sao_Paulo:{outro:%Y%m%d}T150000",
            f"DTEND;TZID=America/Sao_Paulo:{outro:%Y%m%d}T160000",
            "SUMMARY:Fora da janela",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


async def test_parser_inclui_hora_dia_inteiro_e_recorrencia(db, monkeypatch):
    ref = date(2026, 7, 12)
    monkeypatch.setattr(settings, "gcal_ics_url", "https://calendar.test/gcal.ics")

    async def fetch(_url):
        return _ics(ref)

    monkeypatch.setattr(ics_client, "_fetch", fetch)

    eventos, fontes = await ics_client.eventos_do_dia(ref)

    assert fontes == {"gcal": "ok", "outlook": "nao_configurado"}
    assert [evento["titulo"] for evento in eventos] == [
        "Aniversário",
        "Reunião ITER",
        "Reunião semanal",
    ]
    assert [evento["hora"] for evento in eventos] == [None, "09:30", "11:00"]
    assert eventos[0]["inicio_ts"] is None
    assert eventos[1]["inicio_ts"] is not None


async def test_fonte_nao_configurada_nao_faz_rede(db, monkeypatch):
    async def fetch(_url):
        raise AssertionError("a rede não deveria ser chamada")

    monkeypatch.setattr(ics_client, "_fetch", fetch)

    eventos, fontes = await ics_client.eventos_do_dia(date(2026, 7, 12))

    assert eventos == []
    assert fontes == {
        "gcal": "nao_configurado",
        "outlook": "nao_configurado",
    }


async def test_cache_velho_degrada_e_sem_cache_retorna_erro(db, monkeypatch):
    ref = date(2026, 7, 12)
    monkeypatch.setattr(settings, "gcal_ics_url", "https://calendar.test/gcal.ics")

    async def fetch_ok(_url):
        return _ics(ref)

    monkeypatch.setattr(ics_client, "_fetch", fetch_ok)
    eventos, fontes = await ics_client.eventos_do_dia(ref)
    assert eventos
    assert fontes["gcal"] == "ok"
    assert store.get_ics_cache("gcal") is not None

    monkeypatch.setattr(settings, "ics_cache_ttl", 0)

    async def fetch_erro(_url):
        raise RuntimeError("fonte fora do ar")

    monkeypatch.setattr(ics_client, "_fetch", fetch_erro)
    eventos, fontes = await ics_client.eventos_do_dia(ref)
    assert eventos
    assert fontes["gcal"] == "cache"

    monkeypatch.setattr(settings, "gcal_ics_url", "")
    monkeypatch.setattr(
        settings,
        "outlook_ics_url",
        "https://calendar.test/outlook.ics",
    )
    eventos, fontes = await ics_client.eventos_do_dia(ref)
    assert eventos == []
    assert fontes == {"gcal": "nao_configurado", "outlook": "erro"}


async def test_cache_fresco_nao_repete_fetch(db, monkeypatch):
    ref = date(2026, 7, 12)
    monkeypatch.setattr(settings, "gcal_ics_url", "https://calendar.test/gcal.ics")
    chamadas = 0

    async def fetch(_url):
        nonlocal chamadas
        chamadas += 1
        return _ics(ref)

    monkeypatch.setattr(ics_client, "_fetch", fetch)

    primeiro, _ = await ics_client.eventos_do_dia(ref)
    segundo, fontes = await ics_client.eventos_do_dia(ref)

    assert primeiro == segundo
    assert chamadas == 1
    assert fontes["gcal"] == "ok"


def test_get_agenda_mistura_scheduler_e_ics_ordenados(client, monkeypatch):
    # ref no PASSADO de propósito: ref == hoje faria `tarefas_due` vir do mock
    # (não-vazio) e o teste passaria ou quebraria conforme o dia da rodada.
    ref = date.today() - timedelta(days=1)
    quando = datetime.combine(ref, _time(8, 0), tzinfo=TZ).timestamp()
    store.add_schedule(quando, "minha", "Entregar relatório")

    async def eventos(_ref):
        return (
            [
                {
                    "hora": "10:00",
                    "titulo": "Dentista",
                    "fonte": "gcal",
                    "inicio_ts": quando + 7200,
                },
                {
                    "hora": None,
                    "titulo": "Feriado",
                    "fonte": "gcal",
                    "inicio_ts": None,
                },
            ],
            {"gcal": "ok", "outlook": "nao_configurado"},
        )

    monkeypatch.setattr(ics_client, "eventos_do_dia", eventos)

    resposta = client.get("/agenda", params={"data": ref.isoformat()})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert [(item["hora"], item["fonte"]) for item in corpo["eventos"]] == [
        (None, "gcal"),
        ("08:00", "hora_marcada"),
        ("10:00", "gcal"),
    ]
    assert corpo["tarefas_due"] == []


def test_temas_crud_e_digest(client):
    semana = agenda.semana_iso(date.today())

    criada = client.post("/temas", json={"texto": "Preparar planejamento"})
    assert criada.status_code == 200
    tema = criada.json()
    assert tema["semana"] == semana
    assert tema["texto"] == "Preparar planejamento"

    listagem = client.get("/temas")
    assert listagem.status_code == 200
    assert listagem.json() == {"semana": semana, "temas": [tema]}
    assert agenda.linhas_digest(listagem.json()) == [
        "📌 semana: Preparar planejamento"
    ]

    removida = client.delete(f"/temas/{tema['id']}")
    assert removida.status_code == 200
    assert removida.json() == {"ok": True}

    repetida = client.delete(f"/temas/{tema['id']}")
    assert repetida.status_code == 404


def test_post_tasks_com_hora_registra_schedule_e_neutraliza(client):
    ref = date.today()
    area_aberta = next(area for area in tasks.AREAS if not tasks.eh_sensivel(area))

    resposta = client.post(
        "/tasks",
        json={
            "name": "Entregar relatório",
            "area": area_aberta,
            "due": ref.isoformat(),
            "hora": "09:00",
        },
    )
    assert resposta.status_code == 200

    sensivel = client.post(
        "/tasks",
        json={
            "name": "Consulta particular",
            "area": "Corpo",
            "due": ref.isoformat(),
            "hora": "10:00",
        },
    )
    assert sensivel.status_code == 200

    somente_data = client.post(
        "/tasks",
        json={
            "name": "Tarefa sem hora",
            "area": area_aberta,
            "due": ref.isoformat(),
        },
    )
    assert somente_data.status_code == 200

    inicio = datetime.combine(ref, _time.min, tzinfo=TZ).timestamp()
    fim = datetime.combine(
        ref + timedelta(days=1),
        _time.min,
        tzinfo=TZ,
    ).timestamp()
    itens = store.schedules_between(inicio, fim)

    assert [item["ref"] for item in itens] == [
        "Entregar relatório",
        tasks.NEUTRO,
    ]
    assert "Consulta particular" not in [item["ref"] for item in itens]

    so_hora = client.post(
        "/tasks",
        json={
            "name": "Compromisso de hoje",
            "area": area_aberta,
            "hora": "11:00",
        },
    )
    assert so_hora.status_code == 200
    assert len(store.schedules_between(inicio, fim)) == 3

    assert client.post(
        "/tasks",
        json={"name": "Inválida", "area": area_aberta, "due": "12/07/2026"},
    ).status_code == 422
    assert client.post(
        "/tasks",
        json={"name": "Inválida", "area": area_aberta, "hora": "9h"},
    ).status_code == 422


async def test_run_digest_inclui_agenda(db, monkeypatch):
    async def agenda_do_dia(_ref):
        return {
            "data": date.today().isoformat(),
            "eventos": [
                {
                    "hora": "09:15",
                    "titulo": "Reunião",
                    "fonte": "gcal",
                }
            ],
            "temas": [],
            "fontes": {"gcal": "ok", "outlook": "nao_configurado"},
        }

    monkeypatch.setattr(agenda, "do_dia", agenda_do_dia)

    digest = await tasks.run_digest()

    assert "🗓️ 09:15 Reunião" in digest["lines_extra"]


def test_abertura_contem_calendario_e_temas(client, monkeypatch):
    ref = date.today()

    async def agenda_do_dia(_ref, *, incluir_hora_marcada=True):
        assert incluir_hora_marcada is False
        return {
            "data": ref.isoformat(),
            "eventos": [
                {
                    "hora": "14:00",
                    "titulo": "Dentista",
                    "fonte": "gcal",
                    "inicio_ts": None,
                }
            ],
            "temas": [
                {
                    "id": 1,
                    "semana": agenda.semana_iso(ref),
                    "texto": "Fechar orçamento",
                    "criado": 1.0,
                }
            ],
            "fontes": {"gcal": "ok", "outlook": "nao_configurado"},
        }

    monkeypatch.setattr(agenda, "do_dia", agenda_do_dia)

    resposta = client.get("/abertura", params={"data": ref.isoformat()})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["hoje"]["calendario"][0]["titulo"] == "Dentista"
    assert corpo["hoje"]["fontes_calendario"]["gcal"] == "ok"
    assert corpo["temas"][0]["texto"] == "Fechar orçamento"
