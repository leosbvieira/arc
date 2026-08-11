"""A rota que a wiki lê -- e que o app inteiro passa a ler junto."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import ritos, store
from app.config import settings
from app.main import app, require_auth

_SCHEMA_APP = Path(__file__).resolve().parents[2] / "app" / "src" / "wiki-schema.json"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_exige_autenticacao():
    # Sem `with`: o lifespan sobe o worker de captura, e um teste de 401 não
    # tem por que ligar processo de fundo nenhum.
    assert TestClient(app).get("/wiki/parametros").status_code == 401


def test_devolve_os_parametros(client):
    p = client.get("/wiki/parametros").json()
    assert p["tarifas"]["rotina"] == settings.pontos_por_rotina
    assert p["punicao"]["limiar_furos"] == settings.routine_miss_threshold
    assert p["punicao"]["janela"] == "semana_iso"
    assert p["niveis"]["limiares"] == settings.nivel_limiares
    assert p["ciclo"]["semanas"] == settings.ciclo_semanas
    assert p["staging"]["dias_para_alerta"] == settings.staging_age_days
    assert p["shutdown"]["prioridades"] == 3
    assert len(p["areas"]) == 10
    assert [r["slug"] for r in p["ritos"]] == [r["slug"] for r in ritos.RITOS]
    assert p["ritos"][0]["hora"] == ritos.hora(p["ritos"][0]["slug"])


def test_valor_vem_do_settings_nao_de_literal(client, monkeypatch):
    monkeypatch.setattr(settings, "pontos_por_rotina", 999)
    assert client.get("/wiki/parametros").json()["tarifas"]["rotina"] == 999


def test_schema_commitado_bate_com_o_modelo():
    from app.wiki_schema import schema_normalizado
    atual = schema_normalizado()
    commitado = json.loads(_SCHEMA_APP.read_text(encoding="utf-8"))
    assert atual == commitado, "regenere: python -m app.wiki_schema > ../app/src/wiki-schema.json"


def test_normalizacao_nao_deixa_dialeto_do_pydantic():
    from app.wiki_schema import schema_normalizado
    bruto = json.dumps(schema_normalizado())
    for proibido in ("$defs", "$ref", "anyOf", "const", "title", "description"):
        assert proibido not in bruto, f"normalização deixou {proibido}"


def test_so_usa_o_subconjunto_do_caminhador():
    from app.wiki_schema import PALAVRAS, schema_normalizado

    def anda(no):
        assert set(no) <= PALAVRAS, f"palavra fora do subconjunto: {set(no) - PALAVRAS}"
        # `set(no) <= PALAVRAS` sozinho deixa passar um nó `{}` vazio -- conjunto
        # vazio é subconjunto de tudo. O caminhador do app (`confere` em
        # parametrosCore.ts) faz `switch (no.type)`; sem isto o `default` do
        # switch (fail-closed) nunca é exercitado por este teste.
        assert "type" in no, f"nó sem 'type': {no!r}"
        for filho in no.get("properties", {}).values():
            anda(filho)
        if "items" in no:
            anda(no["items"])

    anda(schema_normalizado())
