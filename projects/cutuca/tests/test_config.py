import os

import pytest

from cutuca.config import (
    CadenceRule,
    Config,
    MissingSecret,
    Secrets,
    config_from_dict,
    load_config,
)


def test_config_from_dict_maps_fields():
    data = {
        "owner_chat_id": 42,
        "clickup": {"list_id": "L1", "assignee_overrides": {"joão": "555"}},
        "llm": {"model": "claude-haiku-4-5-20251001", "max_tokens": 300},
        "digest_horarios": ["08:00", "13:00"],
        "escala_tom": False,
        "cobrar_se": {"vence_em_dias": 1, "atrasada": False, "sem_update_dias": 5},
    }
    c = config_from_dict(data)
    assert c.owner_chat_id == 42
    assert c.clickup.list_id == "L1"
    assert c.clickup.assignee_overrides == {"joão": 555}
    assert c.llm.max_tokens == 300
    assert c.digest_horarios == ["08:00", "13:00"]
    assert c.escala_tom is False
    assert c.cobrar_se == CadenceRule(vence_em_dias=1, atrasada=False, sem_update_dias=5)


def test_defaults_are_sane():
    c = config_from_dict({})
    assert c.llm.model == "claude-haiku-4-5-20251001"
    assert c.cobrar_se.vence_em_dias == 0
    assert c.canal == "telegram"


def test_load_example_config():
    here = os.path.dirname(os.path.dirname(__file__))
    c = load_config(os.path.join(here, "config.example.yaml"))
    assert c.clickup.list_id  # placeholder string present
    assert c.llm.model == "claude-haiku-4-5-20251001"


def test_secrets_require_all():
    with pytest.raises(MissingSecret):
        Secrets.from_env({"ANTHROPIC_API_KEY": "x"})  # missing the other two


def test_secrets_from_env_ok():
    s = Secrets.from_env({
        "ANTHROPIC_API_KEY": "a", "TELEGRAM_BOT_TOKEN": "b", "CLICKUP_TOKEN": "c",
    })
    assert (s.anthropic_api_key, s.telegram_bot_token, s.clickup_token) == ("a", "b", "c")
