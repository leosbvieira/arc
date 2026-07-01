"""Wiring for the v0 long-poll host: Telegram listener (Flow A) + APScheduler digest
(Flow B). Heavy libraries (python-telegram-bot, APScheduler) are imported lazily inside
functions so the package imports cleanly under test without them installed.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from . import capture, nudge
from .clickup import ClickUpClient
from .config import Config, Secrets, load_config
from .logging_setup import configure, get_logger, log_event
from .state import NudgeState
from .telegram_channel import TelegramChannel
from .timeutil import get_tz

log = get_logger("cutuca.app")

DEFAULT_CONFIG_PATH = "config.yaml"


class Services:
    """Bundle of wired collaborators shared by both flows."""

    def __init__(self, config: Config, secrets: Secrets):
        self.config = config
        self.secrets = secrets
        tz = get_tz(config.timezone)
        self.clickup = ClickUpClient(secrets.clickup_token, tz=tz)
        self.channel = TelegramChannel(secrets.telegram_bot_token)
        self.state = NudgeState(config.state_db_path)


def build_services(config_path: str = DEFAULT_CONFIG_PATH) -> Services:
    config = load_config(config_path)
    secrets = Secrets.from_env()
    return Services(config, secrets)


# ------------------------------- Flow B (cron) -------------------------------

def run_digest_once(config_path: str = DEFAULT_CONFIG_PATH) -> None:
    """Run one digest and exit. Used by APScheduler jobs and by `python -m cutuca digest`
    (also the entry a Lambda/EventBridge cron would call in the Fase-2 serverless path)."""
    svc = build_services(config_path)
    result = nudge.run_digest(
        clickup=svc.clickup, channel=svc.channel, state=svc.state, config=svc.config
    )
    log_event(log, "digest_run", sent=result.sent, count=result.count)


def _schedule_digests(scheduler, svc: Services) -> None:
    from apscheduler.triggers.cron import CronTrigger  # lazy

    def job():
        nudge.run_digest(
            clickup=svc.clickup, channel=svc.channel, state=svc.state, config=svc.config
        )

    for hhmm in svc.config.digest_horarios:
        hour, minute = (int(p) for p in hhmm.split(":"))
        scheduler.add_job(job, CronTrigger(hour=hour, minute=minute), name=f"digest-{hhmm}")
        log_event(log, "digest_scheduled", at=hhmm, tz=svc.config.timezone)


# ------------------------------ Flow A (listener) ----------------------------

def run(config_path: str = DEFAULT_CONFIG_PATH) -> None:
    """Boot the long-poll listener + scheduler. Blocks until interrupted."""
    from apscheduler.schedulers.background import BackgroundScheduler  # lazy
    from telegram import Update  # lazy
    from telegram.ext import (  # lazy
        Application,
        CommandHandler,
        MessageHandler,
        filters,
    )

    configure()
    svc = build_services(config_path)

    async def on_start(update: "Update", context) -> None:
        chat_id = update.effective_chat.id
        log_event(log, "owner_chat_id", chat_id=chat_id)
        await update.effective_message.reply_text(
            f"cutuca online. Seu chat_id é {chat_id} — cole em config.yaml (owner_chat_id) "
            "pra receber o digest. Agora é só me mandar tarefas."
        )

    async def on_message(update: "Update", context) -> None:
        msg = update.effective_message
        if msg is None or not msg.text:
            return
        chat_id = update.effective_chat.id
        if svc.config.owner_chat_id is None:
            log_event(log, "owner_chat_id", chat_id=chat_id, note="set this in config.yaml")
        reply = await asyncio.to_thread(
            capture.handle_message, msg.text, clickup=svc.clickup, config=svc.config
        )
        await msg.reply_text(reply.text)

    application = Application.builder().token(svc.secrets.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", on_start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    scheduler = BackgroundScheduler(timezone=svc.config.timezone)
    _schedule_digests(scheduler, svc)
    scheduler.start()

    log_event(log, "listener_start", canal=svc.config.canal)
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        scheduler.shutdown(wait=False)
        svc.state.close()
