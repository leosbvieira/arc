"""O Mentor precisa saber do sistema que ele deveria cobrar.

O buraco que isto fecha: `hermes_client.chat` mandava só `MODE_FRAME + texto`.
Perguntar "o que merece meu foco agora?" com 4 tarefas atrasadas na base devolvia
um texto genérico de coach, sem citar nenhuma — enquanto a própria tela promete
"Pense com alguém que conhece o sistema".
"""
import pytest

from app import mentor_contexto, tasks


@pytest.fixture(autouse=True)
def _sem_clickup(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "tasks_source", "mock")


async def test_contexto_lista_as_atrasadas_com_o_atraso(monkeypatch):
    monkeypatch.setattr(tasks, "_open", lambda: [
        tasks._Task("a", "Renovar seguro do carro", "Finance", due_offset=-8),
        tasks._Task("b", "Pagar fatura", "Finance", due_offset=-2),
    ])

    texto = await mentor_contexto.montar()

    assert "Renovar seguro do carro" in texto
    assert "8" in texto and "2" in texto


async def test_contexto_traz_o_placar(monkeypatch):
    monkeypatch.setattr(tasks, "_open", lambda: [])

    texto = await mentor_contexto.montar()

    assert "nível" in texto.lower() or "nivel" in texto.lower()
    assert "ciclo" in texto.lower()


async def test_contexto_diz_explicitamente_quando_nao_ha_atraso(monkeypatch):
    """Silêncio seria ambíguo: o modelo não pode confundir "sem dado" com "em dia"."""
    monkeypatch.setattr(tasks, "_open", lambda: [])

    texto = await mentor_contexto.montar()

    assert "nenhuma tarefa atrasada" in texto.lower()


async def test_contexto_e_compacto(monkeypatch):
    """Vai em TODA mensagem do chat: se crescer sem limite, vira custo e ruído."""
    monkeypatch.setattr(tasks, "_open", lambda: [
        tasks._Task(str(i), f"Tarefa {i}", "Trabalho", due_offset=-i)
        for i in range(1, 40)
    ])

    texto = await mentor_contexto.montar()

    assert len(texto.splitlines()) <= 16
    assert len(texto) <= 1200


async def test_contexto_nunca_derruba_o_chat(monkeypatch):
    """Se a fonte de tarefas cair, o Mentor responde sem contexto — não com erro."""
    def explode():
        raise RuntimeError("clickup fora do ar")

    monkeypatch.setattr(tasks, "_open", explode)

    texto = await mentor_contexto.montar()

    assert isinstance(texto, str)


async def test_chat_injeta_o_contexto_no_prompt(monkeypatch):
    """O elo que faltava: montar o contexto não adianta se o chat não o enviar."""
    from app import hermes_client
    from app.config import settings

    monkeypatch.setattr(settings, "hermes_mock", False)
    prompts: list[str] = []

    async def fake_oneshot(prompt, **_kw):
        prompts.append(prompt)
        return "ok"

    monkeypatch.setattr(hermes_client, "_oneshot", fake_oneshot)

    await hermes_client.chat(
        "o que merece meu foco agora?",
        "Mentor",
        contexto="<estado_do_sistema>\nAtrasadas (1):\n- Renovar seguro [Finance] há 8d\n</estado_do_sistema>",
    )

    assert len(prompts) == 1
    assert "Renovar seguro" in prompts[0]
    assert "o que merece meu foco agora?" in prompts[0]


async def test_chat_sem_contexto_continua_funcionando(monkeypatch):
    """Modos que não precisam de estado (ex.: Capturas) seguem sem custo extra."""
    from app import hermes_client
    from app.config import settings

    monkeypatch.setattr(settings, "hermes_mock", False)
    prompts: list[str] = []

    async def fake_oneshot(prompt, **_kw):
        prompts.append(prompt)
        return "ok"

    monkeypatch.setattr(hermes_client, "_oneshot", fake_oneshot)

    await hermes_client.chat("organize isto", "Capturas")

    assert "estado_do_sistema" not in prompts[0]


async def test_chat_manda_os_turnos_anteriores(monkeypatch):
    """Sem historico, cada mensagem era um subprocesso novo: "e por que?" chegava
    como pergunta orfa, embora a UI desenhasse baloes encadeados."""
    from app import hermes_client
    from app.config import settings

    monkeypatch.setattr(settings, "hermes_mock", False)
    prompts: list[str] = []

    async def fake_oneshot(prompt, **_kw):
        prompts.append(prompt)
        return "ok"

    monkeypatch.setattr(hermes_client, "_oneshot", fake_oneshot)

    await hermes_client.chat(
        "e por quê?",
        "Mentor",
        historico=[
            {"role": "user", "text": "o que merece meu foco?"},
            {"role": "ai", "text": "Pagar a fatura do cartão."},
        ],
    )

    assert "Pagar a fatura do cartão" in prompts[0]
    assert "e por quê?" in prompts[0]


async def test_historico_e_limitado(monkeypatch):
    """O prompt nao pode crescer sem teto: conversa longa viraria custo e latencia."""
    from app import hermes_client
    from app.config import settings

    monkeypatch.setattr(settings, "hermes_mock", False)
    prompts: list[str] = []

    async def fake_oneshot(prompt, **_kw):
        prompts.append(prompt)
        return "ok"

    monkeypatch.setattr(hermes_client, "_oneshot", fake_oneshot)

    historico = [{"role": "user", "text": f"mensagem {i}"} for i in range(40)]
    await hermes_client.chat("agora", "Mentor", historico=historico)

    assert "mensagem 0" not in prompts[0], "as mais antigas caem"
    assert "mensagem 39" in prompts[0], "as recentes ficam"
