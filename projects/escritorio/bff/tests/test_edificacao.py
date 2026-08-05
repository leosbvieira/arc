"""Contratos da edificação mínima e da marca sensível por captura (P2 item 10)."""
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app import capture_pipeline, clickup_client, hermes_client, store, tasks, vault_client
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


async def _fake_write_raw(text, cid, ts=None):
    return f"1- Inbox/Raw/x-{cid}.md"


def _capture_status(cid: int) -> str:
    with closing(store._connect()) as con:
        row = con.execute(
            "SELECT status FROM capture_queue WHERE id = ?",
            (cid,),
        ).fetchone()
    assert row is not None
    return str(row["status"])


@pytest.mark.parametrize(
    ("prefixo", "esperado"),
    [
        ("hack: ", "usar checklist"),
        ("aprendizado: ", "revisar antes de enviar"),
        ("insight: ", "registrar a decisão"),
    ],
)
async def test_hook_aprendizado_nao_classifica_nem_cria_task(
    client,
    monkeypatch,
    prefixo,
    esperado,
):
    monkeypatch.setattr(vault_client, "write_raw", _fake_write_raw)

    async def explode_classify(text):
        pytest.fail("Hermes não deve classificar um aprendizado reconhecível")

    async def explode_create(*args, **kwargs):
        pytest.fail("aprendizado não deve criar task no ClickUp")

    monkeypatch.setattr(hermes_client, "classify", explode_classify)
    monkeypatch.setattr(capture_pipeline, "_create_task", explode_create)

    cid = store.enqueue_capture(f"{prefixo}{esperado}", None)
    row = next(item for item in store.pending_captures() if item["id"] == cid)

    await capture_pipeline._process_one(row)
    assert _capture_status(cid) == "done"

    aprendizados = store.list_aprendizados()
    assert len(aprendizados) == 1
    assert aprendizados[0]["texto"] == esperado
    assert aprendizados[0]["origem_captura_id"] == cid

    # Simula retry com o Raw já persistido. O UNIQUE da origem evita duplicação.
    await capture_pipeline._process_one(
        {
            **row,
            "raw_path": f"1- Inbox/Raw/x-{cid}.md",
        }
    )
    assert len(store.list_aprendizados()) == 1


async def test_prefixo_sensivel_antes_do_aprendizado(client, monkeypatch):
    monkeypatch.setattr(vault_client, "write_raw", _fake_write_raw)

    async def explode_classify(text):
        pytest.fail("Hermes não deve receber um aprendizado reconhecível")

    monkeypatch.setattr(hermes_client, "classify", explode_classify)

    cid = store.enqueue_capture(
        "  Sensível : aprendizado: observar antes de responder",
        None,
    )
    row = next(item for item in store.pending_captures() if item["id"] == cid)
    await capture_pipeline._process_one(row)

    aprendizado = store.list_aprendizados()[0]
    assert aprendizado["texto"] == "observar antes de responder"
    assert aprendizado["sensivel"] == 1

    with closing(store._connect()) as con:
        captura = con.execute(
            "SELECT sensivel FROM capture_queue WHERE id = ?",
            (cid,),
        ).fetchone()
    assert captura["sensivel"] == 1


async def test_captura_sensivel_cria_task_com_tag(client, monkeypatch):
    created = []
    monkeypatch.setattr(vault_client, "write_raw", _fake_write_raw)

    async def fake_classify(text):
        assert text == "marcar consulta"
        return {
            "tipo": "tarefa_pessoal",
            "titulo": "Marcar consulta",
            "quando": None,
        }

    async def fake_find_task_by_marker(list_id, marker):
        return None

    async def fake_create_task(area, nome, due_ts=None, tags=None, description=None):
        created.append(
            {
                "area": area,
                "nome": nome,
                "tags": tags,
                "description": description,
            }
        )
        return {"id": "abc"}

    monkeypatch.setattr(hermes_client, "classify", fake_classify)
    monkeypatch.setattr(
        clickup_client,
        "find_task_by_marker",
        fake_find_task_by_marker,
    )
    monkeypatch.setattr(capture_pipeline, "_create_task", fake_create_task)

    cid = store.enqueue_capture("sensivel: marcar consulta", None)
    row = next(item for item in store.pending_captures() if item["id"] == cid)
    await capture_pipeline._process_one(row)

    assert created
    assert "sensivel" in created[0]["tags"]


def test_digest_neutraliza_task_marcada_sensivel(client):
    task = tasks.Task(
        id="1",
        name="Conteúdo reservado",
        area="Trabalho",
        sensivel=True,
        days_overdue=2,
        severity="atrasado",
    )

    telegram = "\n".join(tasks.render_digest_lines([task], "telegram"))
    app_body = "\n".join(tasks.render_digest_lines([task], "app"))

    assert "Conteúdo reservado" not in telegram
    assert "abre o app" in telegram
    assert "Conteúdo reservado" in app_body


def test_definir_pratica_troca_anterior_e_atualiza_review(client):
    primeiro = store.add_aprendizado("Praticar pausa")
    segundo = store.add_aprendizado("Escrever a próxima ação")

    assert store.definir_pratica(primeiro["id"], _semana_atual())["status"] == "pratica"
    escolhido = store.definir_pratica(segundo["id"], _semana_atual())

    assert escolhido["status"] == "pratica"
    assert escolhido["pratica_semana"] == _semana_atual()
    assert store.get_aprendizado(primeiro["id"])["status"] == "novo"

    edificacao = tasks.weekly_review_pack()["edificacao"]
    assert edificacao["novos"] == 1
    assert edificacao["pratica"]["id"] == segundo["id"]


def _semana_atual() -> str:
    """A prática só vale para a semana em que foi escolhida — fixar "2026-W28" fazia
    o teste passar por acidente enquanto o código ignorava a semana."""
    from app import agenda, tz

    return agenda.semana_iso(tz.hoje_local())


async def test_digest_neutraliza_pratica_sensivel_no_telegram(client):
    aprendizado = store.add_aprendizado(
        "Aplicar a pergunta antes de responder",
        sensivel=True,
    )
    store.definir_pratica(aprendizado["id"], _semana_atual())

    digest = await tasks.run_digest()

    assert "Aplicar a pergunta antes de responder" in digest["body_app"]
    assert "prática da semana definida" in digest["body_telegram"]
    assert "Aplicar a pergunta antes de responder" not in digest["body_telegram"]
    assert any(
        "Aplicar a pergunta antes de responder" in line
        for line in digest["lines_extra"]
    )


def test_endpoints_de_aprendizados(client):
    response = client.post(
        "/aprendizados",
        json={"texto": "  Praticar revisão factual  ", "sensivel": False},
    )
    assert response.status_code == 200
    criado = response.json()
    assert criado["texto"] == "Praticar revisão factual"
    aid = criado["id"]

    response = client.get("/aprendizados", params={"status": "novo"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["aprendizados"]] == [aid]

    response = client.post(f"/aprendizados/{aid}/praticar")
    assert response.status_code == 200
    assert response.json()["status"] == "pratica"
    assert response.json()["pratica_semana"]

    response = client.post(
        f"/aprendizados/{aid}/status",
        json={"status": "aplicado"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "aplicado"

    assert client.get(
        "/aprendizados",
        params={"status": "invalido"},
    ).status_code == 422
    assert client.post(
        "/aprendizados",
        json={"texto": "   "},
    ).status_code == 422
    assert client.post(
        f"/aprendizados/{aid}/status",
        json={"status": "pratica"},
    ).status_code == 422


def test_weekly_review_text_inclui_edificacao_somente_com_novos(client):
    assert "edificação:" not in tasks.weekly_review_text()

    aprendizado = store.add_aprendizado("Escolher uma ação observável")
    texto = tasks.weekly_review_text()
    assert "edificação: 1 aprendizados sem prática — escolher 1 no review" in texto

    store.definir_pratica(aprendizado["id"], "2026-W28")
    assert "edificação:" not in tasks.weekly_review_text()
