"""Consertos da auditoria de 16/ago. Um teste por defeito, nomeado pelo defeito.

Cada conserto tem PELO MENOS UM teste que falha no código de antes — é o que os torna
prova, e não decoração. Os controles negativos (que passam nas duas versões, e existem
para provar que o conserto não quebrou o caminho normal) estão marcados com CONTROLE.
A primeira versão deste arquivo dizia "cada um destes falha antes", o que era falso
para três deles: uma revisão hostil pegou, e frase que não se sustenta em docstring de
teste é pior que frase nenhuma.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import clickup_client, main, store, tasks, vault_client
from app.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "app_password", "senha-de-teste")
    monkeypatch.setattr(settings, "internal_token", "itok")
    store.init_db()
    main._login_erros = {}
    return TestClient(app)


def token(client) -> dict:
    r = client.post("/auth/login", json={"password": "senha-de-teste"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


# --- /auth/login: sem limite de taxa e sem NENHUM rastro ---------------------


def test_senha_errada_deixa_rastro(client):
    # No código de antes, uma tentativa errada não escrevia em lugar nenhum: não havia
    # como saber, depois, que alguém tentou.
    client.post("/auth/login", json={"password": "chute"})
    with store._connect() as con:
        eventos = [
            r["evento"]
            for r in con.execute("SELECT evento FROM telemetry").fetchall()
        ]
    assert "login_falhou" in eventos


def test_login_bloqueia_depois_de_cinco_erros(client):
    for _ in range(main._LOGIN_MAX_ERROS):
        assert client.post("/auth/login", json={"password": "chute"}).status_code == 401
    r = client.post("/auth/login", json={"password": "chute"})
    assert r.status_code == 429
    # E o bloqueio vale mesmo pra senha CERTA — senão o atacante só precisa acertar
    # depois de errar, que é exatamente o que o limite existe pra impedir.
    assert client.post("/auth/login", json={"password": "senha-de-teste"}).status_code == 429


def test_acerto_limpa_o_contador(client):
    for _ in range(3):
        client.post("/auth/login", json={"password": "chute"})
    # ESTE assert e o que discrimina: no codigo de antes nada preenchia o contador,
    # entao checar so que ele esta vazio DEPOIS do acerto passava nas duas versoes.
    assert sum(len(v) for v in main._login_erros.values()) == 3
    assert client.post("/auth/login", json={"password": "senha-de-teste"}).status_code == 200
    assert main._login_erros == {}


# --- /closing/approve: o vault vinha antes do local -------------------------


def test_falha_do_vault_nao_apaga_o_fechamento_do_dia(client, monkeypatch):
    """O rito das 21h é o único que o Leo completa. Perdê-lo inteiro porque o GitHub
    piscou era o pior negócio do sistema: nem rotina, nem ponto, nem fila de retry."""
    hdr = token(client)

    async def vault_caiu(*_a, **_kw):
        raise vault_client.VaultError("vault_indisponivel")

    monkeypatch.setattr(vault_client, "write_raw", vault_caiu)

    body = {
        "template": "yoga",
        "draft_md": "fechei o dia",
        "raw_text": "despejo",
        "checks": [{"rotina": "pesagem", "feito": True}],
    }
    with pytest.raises(vault_client.VaultError):
        client.post("/closing/approve", json=body, headers=hdr)

    # O vault falhou — e MESMO ASSIM a rotina e o ponto ficaram registrados.
    from app import pontos

    hoje = pontos.hoje_local().isoformat()
    assert store.get_checks_on(hoje).get("pesagem") is True
    with store._connect() as con:
        eventos = [
            r["evento"] for r in con.execute("SELECT evento FROM telemetry").fetchall()
        ]
    assert "closing_approved" in eventos


def test_refechar_o_dia_nao_escreve_um_segundo_bloco(client, monkeypatch):
    """O marker levava o sha1 do texto, então editar o despejo e fechar de novo
    produzia marker novo e um SEGUNDO '## Fechamento' na mesma Daily."""
    hdr = token(client)
    appends: list[tuple[str, str]] = []

    async def raw(*_a, **_kw):
        return "1- Inbox/Raw/x.md"

    async def append(path, block, _msg, header_if_new="", dedupe_marker=None,
                     substituir_marcado=False):
        appends.append((path, dedupe_marker))
        return path

    monkeypatch.setattr(vault_client, "write_raw", raw)
    monkeypatch.setattr(vault_client, "append_file", append)

    base = {"template": "yoga", "raw_text": "despejo", "checks": []}
    client.post("/closing/approve", json={**base, "draft_md": "primeira versão"}, headers=hdr)
    client.post("/closing/approve", json={**base, "draft_md": "TEXTO EDITADO"}, headers=hdr)

    assert len(appends) == 2
    # A dedupe do append_file é por marker: se os dois forem iguais, o segundo é no-op
    # no vault. Antes eles diferiam, e o segundo bloco entrava.
    assert appends[0][1] == appends[1][1]
    assert "fechamento:" in appends[0][1]


# --- find_task_by_marker: `None` tinha que ser prova de ausência -------------


async def test_marker_achado_sem_id_estoura_em_vez_de_virar_ausencia(monkeypatch):
    """`None` faz o caller LIBERAR a obra. Achar o marker e não conseguir nomear a
    tarefa não é ausência — devolver None ali criava o segundo resumão que toda a
    máquina de fencing existe pra impedir."""

    async def lista(*_a, **_kw):
        return [{"description": "resumo [book-summary:7:2]", "id": None}]

    monkeypatch.setattr(clickup_client, "_list_tasks", lista)
    with pytest.raises(clickup_client.MarcadorSemId):
        await clickup_client.find_task_by_marker("901327803429", "[book-summary:7:2]")


async def test_ausencia_de_verdade_continua_sendo_none(monkeypatch):
    async def lista(*_a, **_kw):
        return [{"description": "outra coisa", "id": "abc"}]

    monkeypatch.setattr(clickup_client, "_list_tasks", lista)
    assert await clickup_client.find_task_by_marker("901327803429", "[book-summary:7:2]") is None


async def test_a_busca_do_marker_cobre_arquivadas_e_subtarefas(monkeypatch):
    """Um resumão arquivado, ou triado pra debaixo de outra tarefa, lia como ausente."""
    chamadas: list[dict] = []

    async def lista(_client, _list_id, **kwargs):
        chamadas.append(kwargs)
        return []

    monkeypatch.setattr(clickup_client, "_list_tasks", lista)
    await clickup_client.find_task_by_marker("901327803429", "[book-summary:7:2]")

    assert [c["archived"] for c in chamadas] == [False, True], "varre as duas metades"
    assert all(c["subtasks"] for c in chamadas)
    assert all(c["include_closed"] for c in chamadas)


# --- /abertura: uma falha do ClickUp apagava o pack local inteiro ------------


def test_clickup_fora_do_ar_nao_derruba_a_abertura(client, monkeypatch):
    async def clickup_caiu():
        raise RuntimeError("429 rate limited")

    monkeypatch.setattr(tasks, "due_hoje", clickup_caiu)
    r = client.get("/abertura", headers=token(client))

    assert r.status_code == 200, "o pack da manhã é SQLite local; não depende do ClickUp"
    corpo = r.json()
    assert corpo["hoje"]["tarefas_due"] == []
    # E diz que não sabe, em vez de fingir que não há tarefa nenhuma.
    assert corpo["hoje"]["tarefas_indisponivel"] is True
    assert "rotinas_manha" in corpo and "template" in corpo


def test_abertura_normal_nao_marca_indisponivel(client, monkeypatch):
    async def sem_tarefas():
        return []

    monkeypatch.setattr(tasks, "due_hoje", sem_tarefas)
    corpo = client.get("/abertura", headers=token(client)).json()
    assert corpo["hoje"]["tarefas_indisponivel"] is False


# --- vault_client: o módulo que NOMEIA arquivo estava no relógio do processo --


def test_o_path_do_raw_usa_o_fuso_do_leo(monkeypatch):
    """22h BRT num host UTC arquivava em D+1 enquanto a Daily que o referencia é D."""
    from datetime import datetime

    from app.tz import TZ

    # 2026-08-15 22:30 BRT = 2026-08-16 01:30 UTC.
    ts = datetime(2026, 8, 15, 22, 30, tzinfo=TZ).timestamp()
    capturado: dict = {}

    async def get(path):
        capturado["path"] = path
        return {"sha": "x"}  # já existe => write_raw devolve o path e não escreve

    monkeypatch.setattr(vault_client, "_get", get)
    import asyncio

    asyncio.run(vault_client.write_raw("texto", "c1", ts=ts))
    assert "2026-08-15" in capturado["path"], capturado["path"]


def test_o_raw_pede_o_fuso_explicitamente(monkeypatch):
    """Na maquina do Leo o teste acima passaria mesmo no codigo antigo.

    `datetime.fromtimestamp(ts)` sem tz usa o fuso do PROCESSO, que la ja e
    America/Sao_Paulo: a data sairia igual e o teste nao discriminaria nada. O que
    discrimina e exigir que o fuso seja passado de proposito.
    """
    from datetime import datetime as _dt

    from app.tz import TZ

    vistos = []

    class DatetimeEspiao(_dt):
        @classmethod
        def fromtimestamp(cls, ts, tz=None):
            vistos.append(tz)
            return _dt.fromtimestamp(ts, tz)

    async def get(_path):
        return {"sha": "x"}

    monkeypatch.setattr(vault_client, "_get", get)
    monkeypatch.setattr(vault_client, "datetime", DatetimeEspiao)
    import asyncio

    asyncio.run(vault_client.write_raw("t", "c1", ts=1_755_300_000.0))
    assert vistos == [TZ], f"fromtimestamp foi chamado com {vistos}"


def test_days_from_ms_conta_no_fuso_do_leo(monkeypatch):
    """A outra metade do defeito 6, que tinha entrado sem teste nenhum."""
    from datetime import date, datetime as _dt

    from app import clickup_client
    from app.tz import TZ

    vistos = []

    class DatetimeEspiao(_dt):
        @classmethod
        def fromtimestamp(cls, ts, tz=None):
            vistos.append(tz)
            return _dt.fromtimestamp(ts, tz)

    monkeypatch.setattr(clickup_client, "datetime", DatetimeEspiao)
    monkeypatch.setattr(clickup_client, "hoje_local", lambda: date(2026, 8, 16))

    ms = int(_dt(2026, 8, 16, 22, 30, tzinfo=TZ).timestamp() * 1000)
    assert clickup_client.days_from_ms(ms) == 0
    assert vistos == [TZ]


# --- regressoes que a revisao hostil pegou NOS PROPRIOS CONSERTOS ------------


def test_senha_com_acento_nao_derruba_o_login(client, monkeypatch):
    """`secrets.compare_digest` recusa str nao-ASCII com TypeError.

    Trocar o `!=` por ele sem codificar transformou a UNICA porta do app num 500 para
    qualquer senha com acento -- regressao em cima do conserto, e a mais cara possivel
    porque tira o acesso inteiro.
    """
    monkeypatch.setattr(settings, "app_password", "sênha-com-acênto")
    assert client.post("/auth/login", json={"password": "chute"}).status_code == 401
    r = client.post("/auth/login", json={"password": "sênha-com-acênto"})
    assert r.status_code == 200, r.text
    assert r.json()["token"]


def test_o_bloqueio_e_por_origem_e_nao_tranca_o_dono(tmp_path, monkeypatch):
    """O castigo global era uma ARMA: como ele vale tambem pra senha certa, qualquer um
    na rede trancava o app do Leo com 5 requests a cada 5 minutos, sem como destrancar.

    A primeira versao deste teste plantava o contador na mao e so checava que o dono
    entrava -- um contador GLOBAL unico passaria igual. Agora sao dois clientes com
    hosts diferentes, que e o unico jeito de a origem importar.
    """
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "app_password", "senha-de-teste")
    store.init_db()
    main._login_erros = {}

    atacante = TestClient(app, client=("10.0.0.99", 5555))
    dono = TestClient(app, client=("192.168.0.7", 5555))

    for _ in range(main._LOGIN_MAX_ERROS):
        assert atacante.post("/auth/login", json={"password": "chute"}).status_code == 401
    # O atacante tranca A SI MESMO -- inclusive com a senha certa, que e o ponto.
    assert atacante.post("/auth/login", json={"password": "chute"}).status_code == 429
    assert atacante.post("/auth/login", json={"password": "senha-de-teste"}).status_code == 429
    # E o celular do Leo, de outra origem, passa.
    assert dono.post("/auth/login", json={"password": "senha-de-teste"}).status_code == 200


def test_o_429_diz_quanto_esperar(client):
    for _ in range(main._LOGIN_MAX_ERROS):
        client.post("/auth/login", json={"password": "chute"})
    r = client.post("/auth/login", json={"password": "chute"})
    assert r.status_code == 429
    # Sem Retry-After o app nao tem como dizer ao Leo quanto falta, e ele insiste.
    assert int(r.headers["Retry-After"]) > 0


def test_login_nao_conta_como_o_leo_ter_estado_aqui(client):
    """O Modo Retorno (lei 4) le MAX(ts) da telemetria como "o Leo esteve aqui".

    O conserto do login transformou a unica rota SEM autenticacao num produtor dessa
    tabela: sem excluir os eventos de auth, o proprio login zerava `dias_ausente`
    antes de a Home decidir o que mostrar -- e um estranho na rede apagava o sinal.
    """
    import time as _t

    with store._connect() as con:
        con.execute(
            "INSERT INTO telemetry (ts, evento, ref, meta_json) VALUES (?,?,?,?)",
            (_t.time() - 20 * 86400, "capture_in", "1", "{}"),
        )
        con.commit()

    client.post("/auth/login", json={"password": "chute"})
    client.post("/auth/login", json={"password": "senha-de-teste"})
    assert store.dias_desde_ultima_interacao() >= 19


async def test_append_file_substitui_o_bloco_marcado_de_verdade(monkeypatch):
    """O `substituir_marcado` testado no PROPRIO vault_client, nao num fake.

    O teste de ponta a ponta abaixo montava um `append_file` de mentira que CHAMAVA
    `substituir_bloco` -- ou seja, reimplementava o conserto dentro do duble e deixava
    o `append_file` de verdade sem prova nenhuma. Aqui os stubs sao so `_get`/`_put`,
    o padrao que test_vault_client.py ja usa, e o que se observa e o CONTEUDO do PUT.
    """
    import base64

    marker = "<!-- fechamento:2026-08-17 -->"
    atual = (
        "# 2026-08-17\n\n## Manha\n\nmanha\n\n"
        f"## Fechamento (21:00) {marker}\n\nprimeira\n\n## Depois\n\ndepois\n"
    )
    enviado = {}

    async def get(_path):
        return {"sha": "abc", "content": base64.b64encode(atual.encode()).decode()}

    async def put(path, content, message, sha):
        enviado["content"] = content
        return path

    monkeypatch.setattr(vault_client, "_get", get)
    monkeypatch.setattr(vault_client, "_put", put)

    novo = f"## Fechamento (21:30) {marker}\n\nCORRIGIDO\n"
    await vault_client.append_file(
        "Daily/2026-08-17.md", novo, "msg", dedupe_marker=marker, substituir_marcado=True
    )
    corpo = enviado["content"]
    assert corpo.count("## Fechamento") == 1, corpo
    assert "CORRIGIDO" in corpo and "primeira" not in corpo
    assert "manha" in corpo and "depois" in corpo, "os vizinhos nao podem sumir"


async def test_append_file_sem_substituir_continua_idempotente(monkeypatch):
    """O contrapeso: sem a flag, marker presente segue sendo no-op (retry idempotente)."""
    import base64

    marker = "<!-- fechamento:2026-08-17 -->"
    atual = f"# dia\n\n## Fechamento (21:00) {marker}\n\nprimeira\n"
    tocou = {"put": False}

    async def get(_path):
        return {"sha": "abc", "content": base64.b64encode(atual.encode()).decode()}

    async def put(*_a, **_kw):
        tocou["put"] = True
        return "x"

    monkeypatch.setattr(vault_client, "_get", get)
    monkeypatch.setattr(vault_client, "_put", put)
    await vault_client.append_file("Daily/x.md", "novo", "msg", dedupe_marker=marker)
    assert tocou["put"] is False


def test_refechar_com_texto_corrigido_substitui_o_bloco(client, monkeypatch):
    """A dedupe por dia consertou o bloco duplicado e criou um descarte silencioso: o
    segundo approve devolvia sucesso e a correcao nao entrava em lugar nenhum."""
    hdr = token(client)
    nota = {"texto": ""}

    async def raw(*_a, **_kw):
        return "1- Inbox/Raw/x.md"

    async def append(path, block, _msg, header_if_new="", dedupe_marker=None,
                     substituir_marcado=False):
        if dedupe_marker and dedupe_marker in nota["texto"]:
            if substituir_marcado:
                nota["texto"] = vault_client.substituir_bloco(
                    nota["texto"], dedupe_marker, block
                )
        else:
            nota["texto"] = (nota["texto"] + "\n\n" + block).strip()
        return path

    monkeypatch.setattr(vault_client, "write_raw", raw)
    monkeypatch.setattr(vault_client, "append_file", append)

    base = {"template": "yoga", "raw_text": "despejo", "checks": []}
    client.post("/closing/approve", json={**base, "draft_md": "primeira versao"}, headers=hdr)
    client.post("/closing/approve", json={**base, "draft_md": "TEXTO CORRIGIDO"}, headers=hdr)

    assert nota["texto"].count("## Fechamento") == 1, "continua um bloco por dia"
    assert "TEXTO CORRIGIDO" in nota["texto"], "a correcao entrou"
    assert "primeira versao" not in nota["texto"]


def test_agenda_tambem_sobrevive_ao_clickup_fora_do_ar(client, monkeypatch):
    """/abertura ganhou a protecao e /agenda -- o outro chamador de due_hoje -- nao."""

    async def caiu():
        raise RuntimeError("429")

    monkeypatch.setattr(tasks, "due_hoje", caiu)
    r = client.get("/agenda", headers=token(client))
    assert r.status_code == 200
    assert r.json()["tarefas_indisponivel"] is True


def test_o_limite_de_prioridades_segue_a_constante(client, monkeypatch):
    """O pior caso da 1A vivia dentro de um arquivo so.

    `main.PRIORIDADES_SHUTDOWN` era declarado na linha 56 e doze linhas de codigo
    abaixo o validador tinha o literal 3 na mao. Mudar para 4 fazia o push dizer 4 e
    o /wiki/parametros dizer 4, enquanto o POST /shutdown respondia 422 na quarta.
    """
    hdr = token(client)
    monkeypatch.setattr(main, "PRIORIDADES_SHUTDOWN", 4)

    r = client.get("/wiki/parametros", headers=hdr)
    assert r.json()["shutdown"]["prioridades"] == 4

    quatro = {"prioridades": ["a", "b", "c", "d"]}
    assert client.post("/shutdown", json=quatro, headers=hdr).status_code == 200
    cinco = {"prioridades": ["a", "b", "c", "d", "e"]}
    assert client.post("/shutdown", json=cinco, headers=hdr).status_code == 422


def test_o_app_consegue_ver_e_reprocessar_as_capturas_paradas(client):
    """O digest mandava "abrir o app" e abrir o app nao adiantava nada.

    `POST /captures/retry-failed` existia e NENHUMA tela sabia -- grep por
    retry-failed em app/src devolvia zero. O conteudo em questao e coisa que o Leo
    ditou e acredita estar arquivada, porque o /capture responde na hora.
    """
    hdr = token(client)
    cid = store.enqueue_capture("captura que travou", None, "ck-1")
    with store._connect() as con:
        con.execute("UPDATE capture_queue SET status = 'failed' WHERE id = ?", (cid,))
        con.commit()

    assert client.get("/captures/failed", headers=hdr).json()["n"] == 1
    assert client.post("/captures/retry-failed", headers=hdr).json()["requeued"] == 1
    assert client.get("/captures/failed", headers=hdr).json()["n"] == 0


@pytest.fixture
def slot_limpo():
    """O slot do Hermes e estado GLOBAL de modulo, e o pytest-asyncio da um event loop
    novo por teste: um semaforo com waiters de outro loop faz o teste seguinte falhar
    por motivo que nao tem nada a ver com ele. Zerar aqui e explicito de proposito --
    esconder isso numa fixture autouse mascararia que a trava e global de verdade."""
    import asyncio

    from app import hermes_client

    hermes_client._UM_POR_VEZ = asyncio.Semaphore(1)
    hermes_client._esperando_primeiro_plano = 0
    yield
    hermes_client._UM_POR_VEZ = asyncio.Semaphore(1)
    hermes_client._esperando_primeiro_plano = 0


async def test_o_trabalho_de_fundo_cede_a_vez_pro_mentor(slot_limpo):
    """O slot do Hermes e UM so, e `asyncio.Semaphore` e FIFO justo.

    Isso tratava o Leo esperando na frente da tela igual a um worker de fundo: uma
    captura que chegou primeiro segurava o Mentor pelos 150s inteiros dela.

    O teste espera por CONDICAO, nao por relogio. A primeira versao usava sleeps de
    20ms e falhou de forma intermitente com a maquina carregada -- teste que depende de
    timing vira ruido, e ruido acaba sendo ignorado, que e o oposto do que ele serve.
    """
    import asyncio

    from app import hermes_client

    ordem = []
    tentou = set()
    soltar = asyncio.Event()

    async def esperar_por(cond, oque, limite=5.0):
        alvo = asyncio.get_running_loop().time() + limite
        while not cond():
            assert asyncio.get_running_loop().time() < alvo, f"nunca aconteceu: {oque}"
            await asyncio.sleep(0.01)

    async def usa(nome, primeiro_plano, segura=False):
        tentou.add(nome)
        try:
            async with hermes_client._slot(primeiro_plano):
                ordem.append(nome)
                if segura:
                    await soltar.wait()
        except hermes_client.HermesOcupado:
            ordem.append(f"{nome}:RECUSADO")

    # fundo-1 toma o slot e SEGURA ate mandarmos soltar.
    f1 = asyncio.create_task(usa("fundo-1", False, segura=True))
    await esperar_por(lambda: "fundo-1" in ordem, "fundo-1 pegar o slot")

    # fundo-2 tenta entrar ENQUANTO o slot esta tomado. Com a checagem feita uma vez
    # so (a versao errada), ele vira waiter do semaforo aqui e garante o lugar na fila.
    f2 = asyncio.create_task(usa("fundo-2", False))
    await esperar_por(lambda: "fundo-2" in tentou, "fundo-2 tentar")
    await asyncio.sleep(0.15)  # tempo de sobra pra ele parkar, se for parkar

    # O Mentor chega DEPOIS de fundo-2 ja estar na fila. Este e o caso que discrimina:
    # com FIFO cru ele fica atras; com a regra, na frente.
    mentor = asyncio.create_task(usa("mentor", True))
    await esperar_por(lambda: "mentor" in tentou, "mentor tentar")
    await asyncio.sleep(0.15)

    soltar.set()
    await asyncio.gather(f1, f2, mentor)

    assert ordem.index("mentor") < ordem.index("fundo-2"), (
        f"trabalho de fundo que nem tinha comecado passou na frente do Mentor: {ordem}"
    )


async def test_o_mentor_nao_espera_para_sempre_pelo_slot(monkeypatch, slot_limpo):
    """Recusa rapida e explicada vale mais que cinco minutos de "pensando...".

    Sem teto, o app ficava com `sending` travado e a conversa so vive em useState:
    matar o app era a saida, e levava a conversa junto.
    """
    import asyncio

    from app import hermes_client

    monkeypatch.setattr(hermes_client, "_ESPERA_MAX_S", 0.05)

    async def segura():
        async with hermes_client._slot(False):
            await asyncio.sleep(0.5)

    ocupando = asyncio.create_task(segura())
    await asyncio.sleep(0.01)
    with pytest.raises(hermes_client.HermesOcupado):
        async with hermes_client._slot(True):
            pass
    await ocupando


@pytest.mark.hermes_oneshot  # precisa do `_oneshot` DE VERDADE: e nele que o slot mora
def test_o_chat_ocupado_responde_503_e_nao_502(client, monkeypatch, slot_limpo):
    """O caminho INTEIRO, do slot tomado ate o status na resposta.

    A primeira versao deste teste stubava `hermes_client.chat` pra levantar
    `HermesOcupado` -- ou seja, entrava no handler sem passar por `_oneshot`, e por
    isso passava com o codigo errado. Uma revisao hostil montou o cenario de verdade e
    a resposta era 502 "hermes_indisponivel": o `except Exception` do `_oneshot`
    convertia `HermesOcupado` (subclasse de RuntimeError) em `HermesFalhou`.

    Licao embutida no teste: stub que pula a camada onde o bug mora prova nada. Este
    aqui toma o slot de verdade e deixa a excecao subir por todas as camadas -- e por
    isso precisa do marcador `hermes_oneshot`, senao a guarda autouse do conftest
    troca o `_oneshot` inteiro e o teste volta a nao exercitar o slot.
    """
    import asyncio

    from app import hermes_client

    monkeypatch.setattr(settings, "hermes_mock", False)
    monkeypatch.setattr(hermes_client, "_ESPERA_MAX_S", 0.05)
    # Semaforo sem permit nenhum = slot tomado por trabalho de fundo ja em execucao.
    monkeypatch.setattr(hermes_client, "_UM_POR_VEZ", asyncio.Semaphore(0))

    r = client.post(
        "/chat", json={"text": "oi", "mode": "Capturas", "historico": []},
        headers=token(client),
    )
    assert r.status_code == 503, r.json()
    assert r.json()["detail"] == "hermes_ocupado"
    assert r.headers["Retry-After"] == "60"


async def test_a_segunda_copia_do_banco_e_opcional_e_barulhenta(tmp_path, monkeypatch, caplog):
    """O backup padrao grava ao lado do proprio data.db -- mesmo volume do arquivo que
    ele existe pra salvar. E `data.db*` esta no .gitignore, entao nada do que o vault
    nao guarda tem copia fora desta maquina."""
    import asyncio
    import logging

    from app import main as m

    chamadas = []

    def fake_backup(destino, hoje):
        chamadas.append(str(destino))
        if "quebrado" in str(destino):
            raise OSError("pendrive fora")

    monkeypatch.setattr(m.store, "fazer_backup", fake_backup)
    monkeypatch.setattr(m, "INTERVALO_BACKUP_S", 0.01)

    async def uma_rodada():
        tarefa = asyncio.create_task(m._backup_worker())
        await asyncio.sleep(0.05)
        tarefa.cancel()
        try:
            await tarefa
        except asyncio.CancelledError:
            pass

    # Desligado por padrao: so a copia de sempre.
    monkeypatch.setattr(m.settings, "backup_dir_2", "")
    await uma_rodada()
    assert all("quebrado" not in c for c in chamadas)
    primeiro = len(chamadas)
    assert primeiro >= 1

    # Ligado: a segunda copia acontece, e uma falha dela NAO derruba o worker nem
    # impede a principal -- mas deixa rastro, porque backup que falha calado nao existe.
    chamadas.clear()
    monkeypatch.setattr(m.settings, "backup_dir_2", str(tmp_path / "quebrado"))
    with caplog.at_level(logging.ERROR):
        await uma_rodada()
    assert any("quebrado" in c for c in chamadas), chamadas
    assert any("backup 2" in r.message for r in caplog.records)


def test_o_orcamento_do_chat_fecha():
    """A conta do teto, cobrada em vez de afirmada.

    A primeira versao escolheu 30s no olho e o commit AFIRMOU que cabia: nao cabia.
    30 + 150 = 180 contra os 175s do cliente, e isso sem contar o `montar()`, que roda
    antes do slot e busca 10 listas do ClickUp. O cliente abortaria pedido que ia dar
    certo -- o exato defeito que o teto existe pra evitar.

    Este teste existe porque afirmacao em commit message nao segura numero: quem subir
    `hermes_timeout` amanha e nao subir o app junto cai aqui, e nao num spinner.
    """
    from app import hermes_client
    from app.config import settings

    pior_caso_s = (
        hermes_client.MONTAR_MAX_S
        + hermes_client._ESPERA_MAX_S
        + settings.hermes_timeout
        + hermes_client.MARGEM_RESPOSTA_S
    )
    assert pior_caso_s * 1000 <= hermes_client.TETO_CLIENTE_MS, (
        f"o servidor pode levar {pior_caso_s}s e o app desiste em "
        f"{hermes_client.TETO_CLIENTE_MS / 1000}s"
    )


def test_o_teto_do_app_bate_com_o_declarado_no_bff():
    """Os dois lados sao arquivos diferentes em linguagens diferentes; sem esta guarda
    o numero do BFF vira ficcao no dia em que alguem mexer so no TypeScript."""
    import re

    api_ts = (
        Path(__file__).resolve().parents[2] / "app" / "src" / "api.ts"
    ).read_text(encoding="utf-8")
    achado = re.search(r"TIMEOUT_CHAT_MS\s*=\s*([\d_]+);", api_ts)
    assert achado, "TIMEOUT_CHAT_MS sumiu do api.ts"
    from app import hermes_client

    assert int(achado.group(1).replace("_", "")) == hermes_client.TETO_CLIENTE_MS
