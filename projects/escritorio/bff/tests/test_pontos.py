"""Pontos + Conquistas N1-4 (P2 item 3).

A regra do Leo, literal: "punição = PONTOS sobre as Conquistas N1-4 — fazer ganha,
furar desconta POUCO". Estes testes travam exatamente isso: furo isolado NUNCA
desconta, padrão desconta uma vez só, o teto semanal segura o tranco, e o nível é
VITALÍCIO (jamais streak-reset, lei 4).
"""
from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from app import pontos, store, tasks, tz
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    return store


# A TARIFA de produção é a tabela da proposta C2 (rotina 20, fechamento 80, ...),
# e ela existe para o app parar de prometer o que o BFF não paga. Mas os testes
# ABAIXO são sobre a REGRA — furo isolado não desconta, padrão desconta uma vez,
# o teto segura, o nível é vitalício —, e a regra não muda com o preço.
#
# Então esta fixture fixa uma escala didática (rotina = 1, resto = 0) para os
# testes de regra ficarem legíveis: "12 checks = 12 pontos" se lê de cabeça,
# "12 checks = 240 pontos" não. A tarifa REAL é travada por testes próprios, na
# seção "tarifa de produção" no fim do arquivo — se alguém mexer nos números da
# config, é lá que fica vermelho, e o vermelho aponta para a decisão certa.
@pytest.fixture(autouse=True)
def tarifa_didatica(monkeypatch):
    monkeypatch.setattr(settings, "pontos_por_rotina", 1)
    monkeypatch.setattr(settings, "desconto_padrao", 3)
    monkeypatch.setattr(settings, "teto_desconto_semanal", 10)
    for campo in pontos._EVENTOS_PAGOS.values():
        if campo != "pontos_por_rotina":
            monkeypatch.setattr(settings, campo, 0)


# Semana ISO de referência dos testes: 2026-07-06 (segunda) .. 2026-07-12 (domingo).
SEG = date(2026, 7, 6)


def _dia(offset: int) -> str:
    return (SEG + timedelta(days=offset)).isoformat()


def _evento_no_dia(evento: str, ref: str, offset: int = 0) -> None:
    """Grava um evento ao meio-dia local do dia SEG+offset.

    Meio-dia, e não 00:00, para o teste não depender da fronteira do fuso: um
    evento à meia-noite local vira D-1 em UTC e cairia na semana anterior — que
    é justamente o bug que `_REF_E_DATA` evita nos eventos com data na ref.
    """
    quando = datetime.combine(SEG + timedelta(days=offset), time(12, 0), tz.TZ)
    with store._connect() as con:
        con.execute(
            "INSERT INTO telemetry (ts, evento, ref, meta_json) VALUES (?, ?, ?, '{}')",
            (quando.timestamp(), evento, ref),
        )
        con.commit()


def _feito(rotina: str, *offsets: int) -> None:
    for o in offsets:
        store.record_checks(_dia(o), "yoga", [(rotina, True)])


def _furo(rotina: str, *offsets: int) -> None:
    for o in offsets:
        store.record_checks(_dia(o), "yoga", [(rotina, False)])


# --- ganho -------------------------------------------------------------------


def test_ganho_conta_um_ponto_por_rotina_feita(db):
    for i, rotina in enumerate(["academia", "pesagem", "skincare", "diario", "yoga"]):
        _feito(rotina, 0, 1)   # 5 rotinas x 2 dias = 10 checks feitos
    r = pontos.resumo(hoje=SEG + timedelta(days=2))
    assert r["semana"]["ganho"] == 10
    assert r["semana"]["desconto"] == 0
    assert r["semana"]["saldo"] == 10
    assert r["saldo_total"] == 10


# --- furo isolado: a regra mais importante -----------------------------------


def test_furo_isolado_nao_desconta_nada(db):
    _furo("academia", 0)                       # 1 furo
    _furo("pesagem", 0, 1)                     # 2 furos
    _feito("diario", 0, 1, 2)
    r = pontos.resumo(hoje=SEG + timedelta(days=3))
    assert r["semana"]["desconto"] == 0        # nunca por furo isolado (lei 4)
    assert r["semana"]["padroes"] == []
    assert r["semana"]["saldo"] == 3           # só o ganho


# --- padrão: desconta UMA vez por semana por rotina --------------------------


def test_padrao_desconta_uma_vez_so(db):
    _furo("academia", 0, 1, 2)                 # exatamente o limiar (3)
    r = pontos.resumo(hoje=SEG + timedelta(days=6))
    assert r["semana"]["desconto"] == 3
    assert r["semana"]["padroes"] == [
        {"slug": "academia", "nome": "academia", "furos": 3, "delta": -3}
    ]


@pytest.mark.parametrize("n_furos", [3, 4, 5, 6])
def test_mais_furos_na_mesma_rotina_nao_aumentam_o_desconto(db, n_furos):
    _furo("academia", *range(n_furos))
    r = pontos.resumo(hoje=SEG + timedelta(days=6))
    assert r["semana"]["desconto"] == 3        # 1x por semana por rotina, sempre
    assert r["semana"]["padroes"][0]["furos"] == n_furos
    assert r["semana"]["padroes"][0]["delta"] == -3


# --- teto semanal ------------------------------------------------------------


def test_duas_rotinas_em_padrao_descontam_seis(db):
    _furo("academia", 0, 1, 2)
    _furo("pesagem", 0, 1, 2)
    r = pontos.resumo(hoje=SEG + timedelta(days=6))
    assert r["semana"]["desconto"] == 6


def test_teto_semanal_segura_em_dez(db):
    for rotina in ("academia", "pesagem", "skincare", "diario"):
        _furo(rotina, 0, 1, 2)                 # 4 rotinas em padrão = 12 sem teto
    r = pontos.resumo(hoje=SEG + timedelta(days=6))
    assert r["semana"]["desconto"] == 10       # teto, não 12
    assert sum(p["delta"] for p in r["semana"]["padroes"]) == -10
    assert len(r["semana"]["padroes"]) == 4    # todas aparecem, mesmo a que sobrou


def test_alem_do_teto_a_rotina_da_ponta_nao_desconta(db):
    for rotina in ("academia", "diario", "leitura-noturna", "mascara", "pesagem"):
        _furo(rotina, 0, 1, 2)                 # 5 rotinas em padrão
    r = pontos.resumo(hoje=SEG + timedelta(days=6))
    assert r["semana"]["desconto"] == 10
    deltas = {p["slug"]: p["delta"] for p in r["semana"]["padroes"]}
    assert deltas == {
        "academia": -3, "diario": -3, "leitura-noturna": -3,
        "mascara": -1, "pesagem": 0,           # alocação greedy até o teto
    }


# --- dia sem fechamento: linha ausente NÃO é furo ----------------------------


def test_dia_sem_fechamento_nao_conta_furo_nem_ganho(db):
    _feito("academia", 0)
    # dias 1..6 sem NENHUMA linha (viagem, dia quebrado). Nada é gravado.
    r = pontos.resumo(hoje=SEG + timedelta(days=6))
    assert r["semana"]["ganho"] == 1
    assert r["semana"]["desconto"] == 0        # ausência nunca vira punição (lei 4)
    assert r["semana"]["padroes"] == []


# --- nível vitalício ---------------------------------------------------------


def test_nivel_e_vitalicio_mesmo_com_o_saldo_caindo(db, monkeypatch):
    monkeypatch.setattr(settings, "nivel_limiares", [10, 20, 30, 40])
    for i, rotina in enumerate(("academia", "pesagem", "skincare", "diario")):
        _feito(rotina, 0, 1, 2)                # 12 pontos na semana 1 -> N1
    r1 = pontos.resumo(hoje=SEG + timedelta(days=6))
    assert (r1["saldo_total"], r1["pico_total"], r1["nivel"]) == (12, 12, 1)

    # semana 2: 4 rotinas em padrão, ganho zero -> -10 (teto)
    for rotina in ("academia", "pesagem", "skincare", "diario"):
        for o in (7, 8, 9):
            store.record_checks(_dia(o), "yoga", [(rotina, False)])
    r2 = pontos.resumo(hoje=SEG + timedelta(days=13))
    assert r2["saldo_total"] == 2              # caiu abaixo do limiar de N1
    assert r2["pico_total"] == 12              # o pico não regride
    assert r2["nivel"] == 1                    # e o nível TAMBÉM não (jamais reset)
    assert r2["proximo_nivel"] == {"n": 2, "faltam": 8}


def test_proximo_nivel_conta_a_partir_do_saldo(db, monkeypatch):
    monkeypatch.setattr(settings, "nivel_limiares", [10, 20, 30, 40])
    for rotina in ("academia", "pesagem", "skincare", "diario"):
        _feito(rotina, 0, 1, 2)
    r = pontos.resumo(hoje=SEG + timedelta(days=6))
    assert r["proximo_nivel"] == {"n": 2, "faltam": 8}   # 20 - 12


def test_nivel_maximo_nao_tem_proximo(db, monkeypatch):
    monkeypatch.setattr(settings, "nivel_limiares", [1, 2, 3, 4])
    _feito("academia", 0, 1, 2, 3, 4)
    r = pontos.resumo(hoje=SEG + timedelta(days=6))
    assert r["nivel"] == 4
    assert r["proximo_nivel"] is None


def test_saldo_zero_e_n0(db):
    r = pontos.resumo(hoje=SEG)
    assert r["nivel"] == 0 and r["saldo_total"] == 0 and r["pico_total"] == 0


# --- ciclo de 12 semanas -----------------------------------------------------


def test_ciclo_semana_dentro_do_bloco_e_virada(db, monkeypatch):
    monkeypatch.setattr(settings, "ciclo_inicio", "2026-07-06")
    monkeypatch.setattr(settings, "ciclo_semanas", 12)

    c0 = pontos.resumo(hoje=SEG)["ciclo"]
    assert (c0["indice"], c0["semana"], c0["de"]) == (0, 1, 12)

    # última semana do 1º bloco
    c11 = pontos.resumo(hoje=SEG + timedelta(weeks=11, days=3))["ciclo"]
    assert (c11["indice"], c11["semana"]) == (0, 12)

    # virada: 12 semanas depois da âncora, ciclo novo, semana 1
    c12 = pontos.resumo(hoje=SEG + timedelta(weeks=12))["ciclo"]
    assert (c12["indice"], c12["semana"]) == (1, 1)


def test_ciclo_soma_so_as_semanas_do_bloco_corrente(db, monkeypatch):
    monkeypatch.setattr(settings, "ciclo_inicio", "2026-07-06")
    monkeypatch.setattr(settings, "ciclo_semanas", 2)   # bloco curto p/ provar a virada

    _feito("academia", 0, 1, 2)                          # semana 0: +3
    store.record_checks(_dia(14), "yoga", [("academia", True)])   # semana 2: +1

    r = pontos.resumo(hoje=SEG + timedelta(days=14))
    assert r["saldo_total"] == 4                         # a história inteira
    assert r["ciclo"]["indice"] == 1
    assert r["ciclo"]["pontos"] == 1                     # só o bloco corrente


def test_meta_do_ciclo_pondera_dias_da_semana(db, monkeypatch):
    """Rotina de quarta vale 1x/semana; rotina de todo dia vale 7x."""
    monkeypatch.setattr(settings, "ciclo_semanas", 12)
    for r in store.list_routines():
        store.delete_routine(r["id"])
    store.create_routine("todo dia", "manha", dias="*", templates="*")
    store.create_routine("so quarta", "noite", dias="qua", templates="*")

    meta = pontos.resumo(hoje=SEG)["ciclo"]["meta"]
    assert meta == (7 + 1) * 12                          # 8 pts/semana cheia x 12


# --- digest: nome (não slug) + o desconto, factual ---------------------------


def test_digest_usa_o_nome_da_rotina_e_anexa_o_desconto(db):
    _furo("skincare", 0, 1, 2)                 # slug 'skincare', nome 'skincare AM'
    linhas = tasks.routine_lines(today=_dia(3))
    assert linhas == ["🔁 skincare AM: 3 furos em 7d. −3 pts."]
    assert "skincare:" not in linhas[0]         # jamais o slug cru


def test_digest_diz_a_verdade_quando_o_teto_ja_foi_atingido(db):
    for rotina in ("academia", "diario", "leitura-noturna", "mascara", "pesagem"):
        _furo(rotina, 0, 1, 2)
    linhas = tasks.routine_lines(today=_dia(3))
    texto = "\n".join(linhas)
    assert "🔁 pesagem: 3 furos em 7d. (teto semanal atingido, sem desconto)" in texto
    assert "🔁 máscara: 3 furos em 7d. −1 pts." in texto     # o resto do teto
    assert "🔁 academia: 3 furos em 7d. −3 pts." in texto


def test_digest_nunca_e_avaliativo(db):
    _furo("skincare", 0, 1, 2)
    texto = " ".join(tasks.routine_lines(today=_dia(3))).lower()
    for palavra in ("falh", "de novo", "melhor", "vergonh", "again", "streak"):
        assert palavra not in texto


def test_digest_ignora_furo_isolado(db):
    _furo("skincare", 0)
    assert tasks.routine_lines(today=_dia(3)) == []


# --- endpoint ----------------------------------------------------------------


@pytest.fixture
def client(db):
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_pontos_com_base_vazia_nao_explode(client):
    r = client.get("/pontos")
    assert r.status_code == 200
    body = r.json()
    assert body["nivel"] == 0
    assert body["saldo_total"] == 0 and body["pico_total"] == 0
    assert body["semana"] == {
        "ganho": 0,
        "desconto": 0,
        "saldo": 0,
        "padroes": [],
        "teto_desconto": settings.teto_desconto_semanal,
    }
    assert body["ciclo"]["de"] == settings.ciclo_semanas
    assert body["proximo_nivel"]["n"] == 1


def test_pontos_shape_do_contrato(client):
    hoje = date.today()
    seg = hoje - timedelta(days=hoje.weekday())
    for o in range(3):
        d = (seg + timedelta(days=o)).isoformat()
        store.record_checks(d, "yoga", [("skincare", False), ("academia", True)])

    body = client.get("/pontos").json()
    assert set(body) == {
        "nivel", "saldo_total", "pico_total", "ciclo", "semana", "proximo_nivel",
    }
    assert set(body["ciclo"]) == {"indice", "semana", "de", "pontos", "meta"}
    assert set(body["semana"]) == {
        "ganho", "desconto", "saldo", "padroes", "teto_desconto",
    }
    assert body["semana"] == {
        "ganho": 3,
        "desconto": 3,
        "saldo": 0,
        "padroes": [
            {"slug": "skincare", "nome": "skincare AM", "furos": 3, "delta": -3},
        ],
        "teto_desconto": settings.teto_desconto_semanal,
    }


def test_pontos_exige_auth():
    r = TestClient(app).get("/pontos")
    assert r.status_code in (401, 403)


# --- os atos que não são rotina também pagam ---------------------------------
#
# Antes disto o BFF tinha UMA forma de ganhar ponto (rotina marcada no
# fechamento) e o app prometia seis. O ganho continua DERIVADO — agora do log de
# telemetria, que já registrava todos estes atos antes de valerem ponto.


def test_tarefa_concluida_paga(db, monkeypatch):
    monkeypatch.setattr(settings, "pontos_por_tarefa", 10)
    _evento_no_dia("task_completed", "abc123", 0)
    _evento_no_dia("task_completed", "def456", 2)
    assert pontos.resumo(hoje=SEG + timedelta(days=3))["semana"]["ganho"] == 20


def test_a_mesma_tarefa_registrada_duas_vezes_paga_uma(db, monkeypatch):
    """Reabrir e reconcluir é o mesmo ato. O log é append-only; a dedupe é por ref."""
    monkeypatch.setattr(settings, "pontos_por_tarefa", 10)
    _evento_no_dia("task_completed", "abc123", 0)
    _evento_no_dia("task_completed", "abc123", 1)
    assert pontos.resumo(hoje=SEG + timedelta(days=3))["semana"]["ganho"] == 10


def test_fechamento_shutdown_e_despejo_pagam_pela_data_da_ref(db, monkeypatch):
    """Estes três gravam `hoje_local()` na ref, e é a ref que manda.

    Sem isso, um fechamento das 21h num VPS em UTC já está em D+1 — e num domingo
    o dia inteiro pularia para a semana seguinte, tirando o ponto da semana vivida.
    """
    monkeypatch.setattr(settings, "pontos_por_fechamento", 80)
    monkeypatch.setattr(settings, "pontos_por_shutdown", 30)
    monkeypatch.setattr(settings, "pontos_por_despejo", 40)
    # ts propositalmente na semana ERRADA (10 dias depois): a ref tem que vencer.
    _evento_no_dia("closing_approved", _dia(0), 10)
    _evento_no_dia("shutdown", _dia(0), 10)
    _evento_no_dia("despejo_escrito", _dia(0), 10)
    assert pontos.resumo(hoje=SEG + timedelta(days=6))["semana"]["ganho"] == 150


def test_fechar_sem_texto_nao_leva_o_bonus_do_despejo(db, monkeypatch):
    monkeypatch.setattr(settings, "pontos_por_fechamento", 80)
    monkeypatch.setattr(settings, "pontos_por_despejo", 40)
    _evento_no_dia("closing_approved", _dia(0), 0)      # fechou, mas não escreveu
    assert pontos.resumo(hoje=SEG + timedelta(days=1))["semana"]["ganho"] == 80


def test_captura_paga_quando_materializa_nao_quando_enfileira(db, monkeypatch):
    """`capture_done` é o evento do worker; `capture_in` é só o enfileiramento.

    Pagar no enfileiramento pagaria por captura que morre na fila com erro.
    """
    monkeypatch.setattr(settings, "pontos_por_captura", 5)
    _evento_no_dia("capture_in", "1", 0)
    _evento_no_dia("capture_done", "1", 0)
    assert pontos.resumo(hoje=SEG + timedelta(days=1))["semana"]["ganho"] == 5


def test_evento_sem_ref_nao_paga(db, monkeypatch):
    """Sem chave não há dedupe. Evento assim é contador agregado, não ato."""
    monkeypatch.setattr(settings, "pontos_por_tarefa", 10)
    _evento_no_dia("task_completed", "", 0)
    assert pontos.resumo(hoje=SEG + timedelta(days=1))["semana"]["ganho"] == 0


def test_ganho_de_evento_soma_com_o_de_rotina(db, monkeypatch):
    monkeypatch.setattr(settings, "pontos_por_rotina", 20)
    monkeypatch.setattr(settings, "pontos_por_fechamento", 80)
    _feito("academia", 0)
    _feito("pesagem", 0)
    _evento_no_dia("closing_approved", _dia(0), 0)
    assert pontos.resumo(hoje=SEG + timedelta(days=1))["semana"]["ganho"] == 120


def test_evento_conta_para_nivel_e_ciclo_como_qualquer_ganho(db, monkeypatch):
    monkeypatch.setattr(settings, "nivel_limiares", [100, 200, 300, 400])
    monkeypatch.setattr(settings, "ciclo_inicio", "2026-07-06")
    monkeypatch.setattr(settings, "pontos_por_fechamento", 80)
    for o in range(3):
        _evento_no_dia("closing_approved", _dia(o), o)
    r = pontos.resumo(hoje=SEG + timedelta(days=6))
    assert r["pico_total"] == 240
    assert r["nivel"] == 2
    assert r["ciclo"]["pontos"] == 240


def test_semana_de_evento_sozinho_aparece_no_periodo(db, monkeypatch):
    """A semana existe no cálculo mesmo sem NENHUM check de rotina.

    Os laços iteram `checks | reduções | eventos`; sem a união, uma semana em que
    ele só fechou o dia (sem marcar rotina) sumiria do saldo inteiro.
    """
    monkeypatch.setattr(settings, "pontos_por_fechamento", 80)
    _evento_no_dia("closing_approved", _dia(0), 0)
    assert pontos.resumo_periodo(SEG, SEG)["ganho"] == 80
    assert pontos.semana(ref=SEG)["ganho"] == 80


def test_desconto_ainda_morde_um_ganho_que_veio_de_evento(db, monkeypatch):
    monkeypatch.setattr(settings, "pontos_por_fechamento", 80)
    _evento_no_dia("closing_approved", _dia(0), 0)
    _furo("academia", 0, 1, 2)
    r = pontos.resumo(hoje=SEG + timedelta(days=6))["semana"]
    assert (r["ganho"], r["desconto"], r["saldo"]) == (80, 3, 77)


# --- a tarifa de produção ----------------------------------------------------
#
# Os testes acima provam a REGRA com números didáticos. Estes travam os NÚMEROS
# que vão para o aparelho — se alguém mexer na config, é aqui que fica vermelho.


@pytest.fixture
def tarifa_real(tarifa_didatica, monkeypatch):
    """Desfaz a `tarifa_didatica` e devolve a tarifa da proposta C2.

    Depende dela de propósito: sem a dependência explícita, a ordem entre uma
    fixture autouse e uma pedida pelo teste é implícita, e o dia em que ela
    mudasse estes testes passariam a medir a escala errada em silêncio.
    """
    real = {
        "pontos_por_rotina": 20,
        "pontos_por_tarefa": 10,
        "pontos_por_captura": 5,
        "pontos_por_fechamento": 80,
        "pontos_por_shutdown": 30,
        "pontos_por_despejo": 40,
        "desconto_padrao": 60,
        "teto_desconto_semanal": 200,
    }
    for campo, valor in real.items():
        monkeypatch.setattr(settings, campo, valor)
    return real


def test_a_tarifa_do_bff_e_a_tabela_que_o_app_exibe(db, tarifa_real):
    """`app/src/theme.ts` (POINTS) e a config do BFF têm que dizer o mesmo.

    Este teste é a trava do contrato. A tabela do app era display-only e o BFF
    não pagava nada disso: o botão prometia "+80" e o servidor creditava 0.
    """
    from app.config import Settings

    padrao = Settings.model_fields
    for campo, valor in tarifa_real.items():
        assert padrao[campo].default == valor, campo


def test_um_dia_executado_inteiro_vale_duzentos(db, tarifa_real):
    """O dia cheio da proposta: 6 rotinas + fechamento + shutdown, sem despejo."""
    for rotina in ("academia", "pesagem", "skincare", "diario", "yoga", "leitura"):
        _feito(rotina, 0)
    _evento_no_dia("closing_approved", _dia(0), 0)
    _evento_no_dia("shutdown", _dia(0), 0)
    assert pontos.resumo(hoje=SEG)["semana"]["ganho"] == 6 * 20 + 80 + 30


def test_n1_chega_em_dias_e_nao_em_meses(db, tarifa_real):
    """A prova de que os limiares foram calibrados para ESTA escala.

    A 1 ponto por rotina (o que o BFF pagava), N1=700 levaria uns 4 meses de
    execução perfeita. Na tarifa da C2, chega na primeira semana.
    """
    assert sorted(settings.nivel_limiares)[0] == 700
    for o in range(4):
        for rotina in ("academia", "pesagem", "skincare", "diario", "yoga", "leitura"):
            _feito(rotina, o)
        _evento_no_dia("closing_approved", _dia(o), o)
        _evento_no_dia("shutdown", _dia(o), o)
    r = pontos.resumo(hoje=SEG + timedelta(days=4))
    assert r["pico_total"] == 4 * 230
    assert r["nivel"] >= 1


def test_o_desconto_continua_significativo_na_escala_nova(db, tarifa_real):
    """Escalar o ganho sem escalar o desconto mataria a punição em silêncio.

    Um padrão custa 3 rotinas (60), como o Leo travou — não 3 pontos soltos, que
    numa semana de milhares seriam ruído.
    """
    _furo("academia", 0, 1, 2)
    r = pontos.resumo(hoje=SEG + timedelta(days=6))["semana"]
    assert r["desconto"] == 60
    assert r["teto_desconto"] == 200


def test_a_meta_do_ciclo_inclui_os_ritos_diarios(db, tarifa_real, monkeypatch):
    """Sem os ritos no denominador a barra viveria cravada em 100%.

    Fechamento + shutdown + despejo somam 150/dia — mais que as rotinas. Tarefa e
    captura ficam FORA de propósito: não têm cadência, e estimá-las moveria o alvo.
    """
    monkeypatch.setattr(settings, "ciclo_semanas", 12)
    for r in store.list_routines():
        store.delete_routine(r["id"])
    store.create_routine("todo dia", "manha", dias="*", templates="*")

    meta = pontos.resumo(hoje=SEG)["ciclo"]["meta"]
    assert meta == (7 * 20 + 7 * (80 + 30 + 40)) * 12
