"""Config + secrets loading.

Config (non-secret) lives in ``config.yaml``. Secrets live ONLY in the environment
(loaded from ``.env`` by the process manager or python-dotenv). This separation is a
hard rule from the brief: no secret ever touches YAML or code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional


# ----------------------------- config (non-secret) -----------------------------

@dataclass
class LLMConfig:
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 400
    timeout_seconds: int = 20


@dataclass
class ClickUpConfig:
    list_id: str = ""
    assignee_overrides: dict[str, int] = field(default_factory=dict)


@dataclass
class CadenceRule:
    """The 'cobrar_se' predicate. A task is chased if ANY branch matches."""

    vence_em_dias: Optional[int] = 0     # due within N days (None disables)
    atrasada: bool = True                # any overdue
    sem_update_dias: Optional[int] = 3   # untouched for N days (None disables)


@dataclass
class Config:
    owner_chat_id: Optional[int] = None
    clickup: ClickUpConfig = field(default_factory=ClickUpConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    digest_horarios: list[str] = field(default_factory=lambda: ["08:00"])
    timezone: str = "America/Sao_Paulo"
    escala_tom: bool = True
    cobrar_se: CadenceRule = field(default_factory=CadenceRule)
    canal: str = "telegram"
    state_db_path: str = "cutuca_state.db"


def _rule_from(d: dict[str, Any]) -> CadenceRule:
    return CadenceRule(
        vence_em_dias=d.get("vence_em_dias", 0),
        atrasada=bool(d.get("atrasada", True)),
        sem_update_dias=d.get("sem_update_dias", 3),
    )


def config_from_dict(data: dict[str, Any]) -> Config:
    data = data or {}
    cu = data.get("clickup", {}) or {}
    llm = data.get("llm", {}) or {}
    return Config(
        owner_chat_id=data.get("owner_chat_id"),
        clickup=ClickUpConfig(
            list_id=str(cu.get("list_id", "") or ""),
            assignee_overrides={str(k): int(v) for k, v in (cu.get("assignee_overrides") or {}).items()},
        ),
        llm=LLMConfig(
            model=llm.get("model", LLMConfig.model),
            max_tokens=int(llm.get("max_tokens", LLMConfig.max_tokens)),
            timeout_seconds=int(llm.get("timeout_seconds", LLMConfig.timeout_seconds)),
        ),
        digest_horarios=list(data.get("digest_horarios", ["08:00"])),
        timezone=data.get("timezone", "America/Sao_Paulo"),
        escala_tom=bool(data.get("escala_tom", True)),
        cobrar_se=_rule_from(data.get("cobrar_se", {}) or {}),
        canal=data.get("canal", "telegram"),
        state_db_path=data.get("state_db_path", "cutuca_state.db"),
    )


def load_config(path: str) -> Config:
    import yaml  # lazy: keeps pure-logic tests free of PyYAML

    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return config_from_dict(data)


# --------------------------------- secrets -------------------------------------

class MissingSecret(RuntimeError):
    pass


@dataclass
class Secrets:
    anthropic_api_key: str
    telegram_bot_token: str
    clickup_token: str

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> "Secrets":
        env = env if env is not None else os.environ
        missing = [
            k for k in ("ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "CLICKUP_TOKEN")
            if not env.get(k)
        ]
        if missing:
            raise MissingSecret(
                "Missing required secret(s): " + ", ".join(missing)
                + ". Set them in .env / the environment (never in code)."
            )
        return cls(
            anthropic_api_key=env["ANTHROPIC_API_KEY"],
            telegram_bot_token=env["TELEGRAM_BOT_TOKEN"],
            clickup_token=env["CLICKUP_TOKEN"],
        )
