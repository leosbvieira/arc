"""P0.1 — captura livre sem profile deve cair no default `Capturas` (não `Leitura`).

Spec §9 P0. O app manda captura sem profile; o BFF resolve o default de
`settings.hermes_profile_capture`. O default correto é `"Capturas"` (chave existente
no MODE_FRAME); `"Leitura"` era o bug. Testes rodam em mock (sem rede/Hermes).
"""
import app.hermes_client as hc
from app.config import Settings, settings


async def test_captura_sem_profile_usa_capturas(monkeypatch):
    monkeypatch.setattr(settings, "hermes_mock", True)
    monkeypatch.setattr(
        settings,
        "hermes_profile_capture",
        Settings.model_fields["hermes_profile_capture"].default,
    )
    reply = await hc.capture("lembrar de pagar o condominio", None)
    assert reply.startswith("[mock:Capturas]")


async def test_profile_explicito_prevalece(monkeypatch):
    monkeypatch.setattr(settings, "hermes_mock", True)
    reply = await hc.capture("quote pagina 85", "Leitura")
    assert reply.startswith("[mock:Leitura]")


def test_default_config_e_capturas():
    assert Settings.model_fields["hermes_profile_capture"].default == "Capturas"


def test_toda_chave_default_existe_no_mode_frame():
    assert Settings.model_fields["hermes_profile_capture"].default in hc.MODE_FRAME
