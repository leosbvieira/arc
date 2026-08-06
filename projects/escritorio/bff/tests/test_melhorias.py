"""Melhoria não é tarefa: não tem prazo, tem momento.

Capturar "melhorar o filtro de tarefas" hoje cai num de dois buracos: vira
`tarefa_pessoal` → Staging → triagem entre 9 áreas de VIDA (nenhuma é o sistema),
ou vira `nota` e o `capture_pipeline` não cria task nenhuma — o texto fica só no
Raw e nada nunca mais mostra ele. Escreve-e-esquece.

Empurrar melhoria pra lista de tarefas é pior: sem prazo ela cai no bucket
`backlog` da tela Tasks, que é o cemitério — nada cobra, nada lembra. E o que
cobra sem ser acionável vira culpa, que é a inversão de incentivo da auditoria.

Daí a fila separada: sem prazo, sem ClickUp, com ALVO. `app` é acionável só
quando o Leo está programando comigo; `empresa`/`fluxo` só quando ele para pra
pensar em sistema — e disso já existe rito, o review semanal.
"""
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app import agenda, capture_pipeline, hermes_client, pontos, store, vault_client
from app.config import settings
from app.main import app as fastapi_app
from app.main import require_auth


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()


@pytest.fixture
def client():
    fastapi_app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()


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


def _capture_raw_path(cid: int) -> str | None:
    with closing(store._connect()) as con:
        row = con.execute(
            "SELECT raw_path FROM capture_queue WHERE id = ?",
            (cid,),
        ).fetchone()
    assert row is not None
    return row["raw_path"]


def test_melhoria_nasce_nova_e_sem_alvo():
    """Captura não obriga a decidir o alvo na hora — decidir é atrito."""
    melhoria = store.add_melhoria("o filtro de tarefas devia lembrar o último")

    assert melhoria["texto"] == "o filtro de tarefas devia lembrar o último"
    assert melhoria["alvo"] is None
    assert melhoria["status"] == "novo"


def test_melhoria_aceita_alvo_na_criacao():
    melhoria = store.add_melhoria("cachear o dashboard", alvo="empresa")

    assert melhoria["alvo"] == "empresa"


def test_alvo_invalido_nao_entra_no_banco():
    """Alvo livre viraria taxonomia informal e a fila deixaria de ser filtrável."""
    with pytest.raises(ValueError, match="alvo_melhoria_invalido"):
        store.add_melhoria("qualquer coisa", alvo="pessoal")

    assert store.list_melhorias() == []


def test_origem_da_captura_torna_o_retry_idempotente():
    """Mesma garantia do aprendizado: retry da fila não duplica o item."""
    primeira = store.add_melhoria("texto", origem_captura_id=7)
    segunda = store.add_melhoria("texto", origem_captura_id=7)

    assert primeira["id"] == segunda["id"]
    assert len(store.list_melhorias()) == 1


def test_listagem_filtra_por_alvo_e_por_status():
    store.add_melhoria("do app", alvo="app")
    store.add_melhoria("da empresa", alvo="empresa")
    sem_alvo = store.add_melhoria("a triar")
    store.set_status_melhoria(sem_alvo["id"], "descartada")

    assert [m["texto"] for m in store.list_melhorias(alvo="app")] == ["do app"]
    assert [m["texto"] for m in store.list_melhorias(status="novo")] == [
        "da empresa",
        "do app",
    ]


def test_definir_alvo_depois_da_captura():
    melhoria = store.add_melhoria("a triar")

    atualizada = store.definir_alvo(melhoria["id"], "fluxo")

    assert atualizada["alvo"] == "fluxo"
    assert store.definir_alvo(99999, "app") is None


def test_escolher_da_semana_desmarca_a_anterior():
    """Uma por vez. Duas escolhas simultâneas é o mesmo que nenhuma."""
    antiga = store.add_melhoria("antiga", alvo="empresa")
    nova = store.add_melhoria("nova", alvo="fluxo")

    store.escolher_melhoria(antiga["id"], "2026-W32")
    store.escolher_melhoria(nova["id"], "2026-W32")

    assert store.get_melhoria(antiga["id"])["status"] == "novo"
    assert store.get_melhoria(antiga["id"])["escolhida_semana"] is None
    escolhida = store.get_melhoria(nova["id"])
    assert escolhida["status"] == "escolhida"
    assert escolhida["escolhida_semana"] == "2026-W32"


def test_melhoria_ja_resolvida_nao_volta_pra_semana():
    """Escolher uma feita/descartada reabriria trabalho que o Leo já encerrou."""
    feita = store.add_melhoria("feita", alvo="empresa")
    store.set_status_melhoria(feita["id"], "feita")
    descartada = store.add_melhoria("descartada", alvo="empresa")
    store.set_status_melhoria(descartada["id"], "descartada")

    assert store.escolher_melhoria(feita["id"], "2026-W32") is None
    assert store.escolher_melhoria(descartada["id"], "2026-W32") is None
    assert store.get_melhoria(feita["id"])["status"] == "feita"


def test_escolhida_nao_e_status_manual():
    """Entrar em `escolhida` exige semana; sem ela o review não sabe se venceu."""
    melhoria = store.add_melhoria("x", alvo="empresa")

    with pytest.raises(ValueError, match="status_melhoria_invalido"):
        store.set_status_melhoria(melhoria["id"], "escolhida")


def test_paradas_ignoram_as_do_app():
    """`app` é minha, não dele: contar no "escolhe 1" recria a pilha de culpa.

    Ele captura melhoria de app o tempo todo — se cada uma engrossasse o nudge do
    review, o número viraria dívida e a tela pararia de ser aberta."""
    store.add_melhoria("melhoria do app", alvo="app")
    store.add_melhoria("melhoria da empresa", alvo="empresa")
    store.add_melhoria("melhoria de fluxo", alvo="fluxo")
    store.add_melhoria("ainda sem alvo")

    paradas = [m["texto"] for m in store.melhorias_paradas()]

    assert "melhoria do app" not in paradas
    assert set(paradas) == {
        "melhoria da empresa",
        "melhoria de fluxo",
        "ainda sem alvo",
    }


def test_parada_deixa_de_contar_quando_e_escolhida():
    empresa = store.add_melhoria("da empresa", alvo="empresa")

    store.escolher_melhoria(empresa["id"], "2026-W32")

    assert store.melhorias_paradas() == []


# --- a semana da escolha VENCE ------------------------------------------------
#
# `escolhida_semana` era gravada e nunca comparada — o mesmo defeito que
# `pratica_da_semana` existe para consertar na edificação, cujo comentário do fix
# está oito linhas acima do código que eu escrevi em tasks.py. Sem o filtro, uma
# escolha de junho segue anunciada como "a melhoria DESTA semana" em agosto, e
# como a tela usa ternário encadeado (escolhida ? … : paradas ? …), o convite
# "escolher 1" nunca mais é renderizado. A fila trava em silêncio.


def test_escolha_de_semana_passada_nao_e_a_da_semana():
    antiga = store.add_melhoria("escolhida em junho", alvo="empresa")
    store.escolher_melhoria(antiga["id"], "2026-W26")

    assert store.melhoria_da_semana("2026-W32") is None
    assert store.melhoria_da_semana("2026-W26")["id"] == antiga["id"]


def test_escolha_vencida_vira_pergunta_em_vez_de_sumir():
    """Não se apaga a escolha: ela vira "fez?", como praticas_sem_avaliacao."""
    antiga = store.add_melhoria("escolhida em junho", alvo="empresa")
    store.escolher_melhoria(antiga["id"], "2026-W26")

    vencidas = store.melhorias_vencidas("2026-W32")

    assert [m["id"] for m in vencidas] == [antiga["id"]]
    assert store.get_melhoria(antiga["id"])["status"] == "escolhida"


def test_escolha_da_semana_corrente_nao_esta_vencida():
    atual = store.add_melhoria("desta semana", alvo="fluxo")
    store.escolher_melhoria(atual["id"], "2026-W32")

    assert store.melhorias_vencidas("2026-W32") == []
    assert store.melhoria_da_semana("2026-W32")["id"] == atual["id"]


# --- a triar não é escolhível --------------------------------------------------
#
# O CTA do review dizia "escolher 1 para a semana" contando também os itens sem
# alvo — mas na tela eles caem em "a triar", cujo card não tem o botão de
# escolher. O texto prometia uma ação que a tela de destino não oferecia.


def test_paradas_separam_o_que_e_triagem_do_que_e_escolha():
    store.add_melhoria("ainda sem alvo")
    store.add_melhoria("outra sem alvo")
    store.add_melhoria("da empresa", alvo="empresa")

    assert len(store.melhorias_a_triar()) == 2
    assert [m["texto"] for m in store.melhorias_escolhiveis()] == ["da empresa"]
    # `paradas` continua sendo o total das duas — é o número que ele vê.
    assert len(store.melhorias_paradas()) == 3


# --- hook de captura ---------------------------------------------------------
#
# Sem hook, "melhorar o filtro" é indistinguível de "comprar pão" para o
# classificador. O prefixo resolve a intenção ANTES do Hermes: determinístico,
# sem pagar inferência e sem depender de acerto probabilístico.


@pytest.mark.parametrize(
    ("texto", "esperado", "alvo"),
    [
        ("melhoria: trocar o botão", "trocar o botão", None),
        ("melhoria app: filtro lembra o último", "filtro lembra o último", "app"),
        ("melhoria empresa: cachear o dashboard", "cachear o dashboard", "empresa"),
        ("melhoria fluxo: onboarding em 2 passos", "onboarding em 2 passos", "fluxo"),
        ("MELHORIA APP: caixa alta também", "caixa alta também", "app"),
    ],
)
async def test_hook_vira_melhoria_sem_task_e_sem_hermes(
    monkeypatch,
    texto,
    esperado,
    alvo,
):
    gravado_no_vault: list[tuple[int, str]] = []

    async def espiar_write_raw(text, cid, ts=None):
        gravado_no_vault.append((cid, text))
        return f"1- Inbox/Raw/x-{cid}.md"

    monkeypatch.setattr(vault_client, "write_raw", espiar_write_raw)

    async def explode_classify(text):
        pytest.fail("Hermes não deve classificar uma melhoria reconhecível")

    async def explode_create(*args, **kwargs):
        pytest.fail("melhoria não deve criar task no ClickUp")

    monkeypatch.setattr(hermes_client, "classify", explode_classify)
    monkeypatch.setattr(capture_pipeline, "_create_task", explode_create)

    cid = store.enqueue_capture(texto, None)
    row = next(item for item in store.pending_captures() if item["id"] == cid)

    await capture_pipeline._process_one(row)

    assert _capture_status(cid) == "done"
    melhorias = store.list_melhorias()
    assert len(melhorias) == 1
    assert melhorias[0]["texto"] == esperado
    assert melhorias[0]["alvo"] == alvo
    assert melhorias[0]["origem_captura_id"] == cid

    # Lei 1: o Raw sai ANTES do hook, verbatim e COM o prefixo. Sem esta asserção,
    # um "otimizador" que pulasse o commit do vault para melhorias passava na suíte
    # inteira — e aí uma falha entre o write e o add_melhoria perderia o texto.
    assert gravado_no_vault == [(cid, texto)]
    assert _capture_raw_path(cid) == f"1- Inbox/Raw/x-{cid}.md"


async def test_retry_da_captura_nao_duplica_a_melhoria(monkeypatch):
    monkeypatch.setattr(vault_client, "write_raw", _fake_write_raw)

    cid = store.enqueue_capture("melhoria app: x", None)
    row = next(item for item in store.pending_captures() if item["id"] == cid)

    await capture_pipeline._process_one(row)
    await capture_pipeline._process_one({**row, "raw_path": f"1- Inbox/Raw/x-{cid}.md"})

    assert len(store.list_melhorias()) == 1


async def test_prefixo_sensivel_viaja_ate_a_melhoria(monkeypatch):
    """Lei 7 fail-closed: a marca precisa chegar na fila, senão o preview vaza."""
    monkeypatch.setattr(vault_client, "write_raw", _fake_write_raw)

    cid = store.enqueue_capture("sensivel: melhoria empresa: assunto delicado", None)
    row = next(item for item in store.pending_captures() if item["id"] == cid)

    await capture_pipeline._process_one(row)

    melhoria = store.list_melhorias()[0]
    assert melhoria["texto"] == "assunto delicado"
    assert melhoria["alvo"] == "empresa"
    assert melhoria["sensivel"] == 1


async def test_palavra_no_meio_da_frase_nao_dispara_o_hook(monkeypatch):
    """O hook é um prefixo, não uma busca: 'pensei numa melhoria: x' é captura normal."""
    monkeypatch.setattr(vault_client, "write_raw", _fake_write_raw)

    async def classify_como_nota(text):
        return {"tipo": "nota", "titulo": None, "quando": None}

    monkeypatch.setattr(hermes_client, "classify", classify_como_nota)

    cid = store.enqueue_capture("pensei numa melhoria: trocar o botão", None)
    row = next(item for item in store.pending_captures() if item["id"] == cid)

    await capture_pipeline._process_one(row)

    assert store.list_melhorias() == []


async def test_alvo_desconhecido_nao_e_engolido_como_melhoria(monkeypatch):
    """`melhoria xyz:` cai na captura normal em vez de virar melhoria sem alvo.

    Preferir o caminho normal a inventar um alvo: o Raw preserva o texto e a
    tarefa aparece na triagem, onde ele vê. Engolir criaria uma melhoria cujo
    texto começaria com 'xyz:' — ruído silencioso."""
    monkeypatch.setattr(vault_client, "write_raw", _fake_write_raw)

    async def classify_como_nota(text):
        return {"tipo": "nota", "titulo": None, "quando": None}

    monkeypatch.setattr(hermes_client, "classify", classify_como_nota)

    cid = store.enqueue_capture("melhoria sistema: trocar o botão", None)
    row = next(item for item in store.pending_captures() if item["id"] == cid)

    await capture_pipeline._process_one(row)

    assert store.list_melhorias() == []


@pytest.mark.parametrize("texto", ["melhoria:", "melhoria:   ", "melhoria app:"])
async def test_prefixo_sem_texto_nao_vira_melhoria_vazia(monkeypatch, texto):
    """Ditado cortado / envio acidental não pode virar card em branco.

    A borda HTTP já rejeita texto vazio com 422, mas o caminho da fila — que é o
    que recebe entrada não controlada (voz, Telegram) — entrava sem guarda. O
    resultado era um card vazio impossível de triar engrossando o "escolher 1" do
    review. Cai no caminho normal, como já acontece com `melhoria xyz:`."""
    monkeypatch.setattr(vault_client, "write_raw", _fake_write_raw)

    async def classify_como_nota(text):
        return {"tipo": "nota", "titulo": None, "quando": None}

    monkeypatch.setattr(hermes_client, "classify", classify_como_nota)

    cid = store.enqueue_capture(texto, None)
    row = next(item for item in store.pending_captures() if item["id"] == cid)

    await capture_pipeline._process_one(row)

    assert store.list_melhorias() == []


async def test_ideia_nao_e_mais_hook_de_melhoria(monkeypatch):
    """`ideia` já era palavra da casa — sequestrá-la fazia perder compromisso.

    `ideia:` é um dos modos da gramática de leitura (CAPTURE-GRAMMAR-SPEC.md) e a
    própria tela de Captura manda dizer "ideia" no ditado. Com o hook, "ideia:
    levar a Maria pra jantar sexta" nunca chegava ao classificador: sem data
    parseada, sem card, sem lembrete — e o recibo continuava sendo "✅ anotado"."""
    monkeypatch.setattr(vault_client, "write_raw", _fake_write_raw)
    vistos: list[str] = []

    async def classify_normal(text):
        vistos.append(text)
        return {"tipo": "tarefa_pessoal", "titulo": "Jantar com a Maria", "quando": None}

    async def fake_create(area, nome, **kwargs):
        return {"id": "task-1"}

    monkeypatch.setattr(hermes_client, "classify", classify_normal)
    monkeypatch.setattr(capture_pipeline, "_create_task", fake_create)
    monkeypatch.setattr(
        capture_pipeline.clickup_client,
        "find_task_by_marker",
        lambda *a, **k: _nada(),
    )

    cid = store.enqueue_capture("ideia: levar a Maria pra jantar sexta", None)
    row = next(item for item in store.pending_captures() if item["id"] == cid)

    await capture_pipeline._process_one(row)

    assert store.list_melhorias() == []
    assert vistos == ["ideia: levar a Maria pra jantar sexta"]


async def _nada():
    return None


# --- endpoints ---------------------------------------------------------------


def test_fila_comeca_vazia(client):
    corpo = client.get("/melhorias").json()

    assert corpo["melhorias"] == []
    # A semana viaja com a lista: a tela precisa dela para saber se a escolhida é
    # DESTA semana, e recalcular data no cliente é como o projeto já errou antes.
    assert corpo["semana"] == agenda.semana_iso(pontos.hoje_local())


def test_criar_pelo_app_sem_passar_pela_captura(client):
    resposta = client.post("/melhorias", json={"texto": "cachear o dashboard"})

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "novo"
    assert resposta.json()["alvo"] is None


def test_texto_em_branco_nao_vira_melhoria(client):
    """Espaços isolados não constituem melhoria — mesma guarda do aprendizado."""
    assert client.post("/melhorias", json={"texto": "   "}).status_code == 422


def test_alvo_invalido_barrado_na_borda(client):
    resposta = client.post("/melhorias", json={"texto": "x", "alvo": "pessoal"})

    assert resposta.status_code == 422
    assert client.get("/melhorias").json()["melhorias"] == []


def test_listagem_aceita_filtro_de_alvo(client):
    client.post("/melhorias", json={"texto": "do app", "alvo": "app"})
    client.post("/melhorias", json={"texto": "da empresa", "alvo": "empresa"})

    resposta = client.get("/melhorias", params={"alvo": "app"})

    assert [m["texto"] for m in resposta.json()["melhorias"]] == ["do app"]
    assert client.get("/melhorias", params={"alvo": "xpto"}).status_code == 422


def test_definir_alvo_pela_api(client):
    id_melhoria = client.post("/melhorias", json={"texto": "a triar"}).json()["id"]

    resposta = client.post(f"/melhorias/{id_melhoria}/alvo", json={"alvo": "fluxo"})

    assert resposta.status_code == 200
    assert resposta.json()["alvo"] == "fluxo"
    assert client.post("/melhorias/9999/alvo", json={"alvo": "app"}).status_code == 404


def test_escolher_usa_a_semana_corrente_do_servidor(client):
    """A semana não vem do cliente: relógio de celular errado gravaria a semana errada."""
    id_melhoria = client.post(
        "/melhorias",
        json={"texto": "x", "alvo": "empresa"},
    ).json()["id"]

    resposta = client.post(f"/melhorias/{id_melhoria}/escolher")

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "escolhida"
    assert resposta.json()["escolhida_semana"] == agenda.semana_iso(pontos.hoje_local())


def test_escolher_o_que_ja_foi_resolvido_e_404(client):
    id_melhoria = client.post("/melhorias", json={"texto": "x"}).json()["id"]
    client.post(f"/melhorias/{id_melhoria}/status", json={"status": "feita"})

    assert client.post(f"/melhorias/{id_melhoria}/escolher").status_code == 404


def test_marcar_feita_e_descartada(client):
    id_melhoria = client.post("/melhorias", json={"texto": "x"}).json()["id"]

    resposta = client.post(f"/melhorias/{id_melhoria}/status", json={"status": "feita"})

    assert resposta.json()["status"] == "feita"
    assert client.post(
        f"/melhorias/{id_melhoria}/status",
        json={"status": "escolhida"},
    ).status_code == 422
    assert client.post(
        "/melhorias/9999/status",
        json={"status": "feita"},
    ).status_code == 404


# --- superfície do review ----------------------------------------------------
#
# O rito onde ele já para pra pensar em sistema é o review. Sem isso a fila é só
# mais uma tela que ele não abre — e ele é procrastinador por autodeclaração.


def test_marca_sensivel_do_formulario_chega_ao_registro(client):
    """O checkbox da tela é a única marcação de lei 7 que a fila carrega."""
    criada = client.post(
        "/melhorias",
        json={"texto": "assunto delicado", "sensivel": True},
    ).json()

    assert criada["sensivel"] == 1
    assert client.get("/melhorias").json()["melhorias"][0]["sensivel"] == 1


def test_review_semanal_conta_as_paradas_e_a_escolhida(client):
    from app import tasks

    client.post("/melhorias", json={"texto": "da empresa", "alvo": "empresa"})
    client.post("/melhorias", json={"texto": "do app", "alvo": "app"})
    escolhida = client.post(
        "/melhorias",
        json={"texto": "de fluxo", "alvo": "fluxo"},
    ).json()
    client.post(f"/melhorias/{escolhida['id']}/escolher")

    pack = tasks.weekly_review_pack()

    assert pack["melhorias"]["paradas"] == 1
    assert pack["melhorias"]["escolhida"]["texto"] == "de fluxo"
    assert pack["melhorias"]["app"] == 1
    assert pack["melhorias"]["vencidas"] == []


def test_review_nao_serve_escolha_de_outra_semana(client):
    """O bug que cinco revisores acharam: a escolha de junho travava o convite."""
    from app import tasks

    antiga = client.post(
        "/melhorias",
        json={"texto": "escolhida em junho", "alvo": "empresa"},
    ).json()
    store.escolher_melhoria(antiga["id"], "2026-W26")
    client.post("/melhorias", json={"texto": "nova da semana", "alvo": "fluxo"})

    pack = tasks.weekly_review_pack()

    assert pack["melhorias"]["escolhida"] is None, "junho não é 'a desta semana'"
    assert [m["texto"] for m in pack["melhorias"]["vencidas"]] == ["escolhida em junho"]
    # E o convite volta a aparecer, que é o que estava travado.
    assert pack["melhorias"]["escolhiveis"] == 1


def test_texto_do_review_cobra_escolha_sem_cobrar_as_do_app(client):
    from app import tasks

    client.post("/melhorias", json={"texto": "da empresa", "alvo": "empresa"})
    for n in range(5):
        client.post("/melhorias", json={"texto": f"app {n}", "alvo": "app"})

    texto = tasks.weekly_review_text()

    assert "1 melhoria parada" in texto
    # As 5 do app aparecem como informação, nunca no formato de cobrança.
    assert "5 pro Claude" in texto
    assert "6 melhorias" not in texto


def test_texto_do_review_pede_triagem_quando_nao_ha_o_que_escolher(client):
    """Não prometer uma ação que a tela de destino não oferece.

    O card de "a triar" só tem os chips de alvo; o botão "fazer esta semana" mora
    no card da fila. Dizer "escolher 1" quando tudo está a triar mandava o Leo
    procurar um botão que não existe naquela seção."""
    from app import tasks

    client.post("/melhorias", json={"texto": "sem alvo 1"})
    client.post("/melhorias", json={"texto": "sem alvo 2"})

    texto = tasks.weekly_review_text()

    assert "2 melhorias a triar" in texto
    assert "escolher 1" not in texto


def test_texto_do_review_pergunta_pela_escolha_vencida(client):
    from app import tasks

    antiga = client.post(
        "/melhorias",
        json={"texto": "escolhida em junho", "alvo": "empresa"},
    ).json()
    store.escolher_melhoria(antiga["id"], "2026-W26")

    texto = tasks.weekly_review_text()

    assert "2026-W26" in texto
    # Lei 4: factual, nunca julgamento.
    for palavra in ("atrasad", "furou", "falhou", "deveria"):
        assert palavra not in texto.lower()


def test_texto_sensivel_de_melhoria_nunca_entra_no_texto_do_review(client):
    """Lei 7: weekly_review_text() vira artefato no vault E texto de nudge.

    O texto inteiro do nudge aparece no lockscreen. O pack (`/review/weekly`, atrás
    do login) pode carregar o objeto inteiro; o TEXTO só pode carregar contagem."""
    from app import tasks

    criada = client.post(
        "/melhorias",
        json={"texto": "renegociar a dívida do cartão", "alvo": "empresa", "sensivel": True},
    ).json()
    store.escolher_melhoria(criada["id"], "2026-W26")

    texto = tasks.weekly_review_text()

    assert "dívida" not in texto
    assert "cartão" not in texto
