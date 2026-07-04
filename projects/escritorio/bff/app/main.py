from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel

from . import hermes_client, push, store, tasks
from .auth import make_token, require_auth
from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    yield


app = FastAPI(title="escritório BFF", lifespan=lifespan)


class LoginIn(BaseModel):
    password: str


class TokenOut(BaseModel):
    token: str


class CaptureIn(BaseModel):
    text: str
    profile: str | None = None


class CaptureOut(BaseModel):
    reply: str


class DeviceIn(BaseModel):
    token: str


class NotifyIn(BaseModel):
    title: str = "Escritório"
    body: str


class CreateTaskIn(BaseModel):
    name: str
    area: str


@app.get("/health")
async def health():
    return {"ok": True, "mock": settings.hermes_mock}


@app.post("/auth/login", response_model=TokenOut)
async def login(body: LoginIn):
    if body.password != settings.app_password:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "senha incorreta")
    return TokenOut(token=make_token())


@app.post("/capture", response_model=CaptureOut)
async def capture(body: CaptureIn, _: str = Depends(require_auth)):
    reply = await hermes_client.capture(body.text, body.profile)
    return CaptureOut(reply=reply)


@app.post("/devices")
async def register_device(body: DeviceIn, _: str = Depends(require_auth)):
    store.add_device(body.token)
    return {"ok": True, "count": len(store.list_devices())}


@app.get("/tasks")
async def get_tasks(_: str = Depends(require_auth)):
    return await tasks.list_by_area()


@app.post("/tasks")
async def create_task(body: CreateTaskIn, _: str = Depends(require_auth)):
    if body.area not in tasks.AREAS:
        raise HTTPException(422, f"área inválida; use {tasks.AREAS}")
    t = await tasks.create(body.name, body.area)
    return t.model_dump()


@app.post("/tasks/{task_id}/complete")
async def complete_task(task_id: str, _: str = Depends(require_auth)):
    ok = await tasks.complete(task_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task não encontrada")
    return {"ok": True}


@app.get("/digest")
async def get_digest(_: str = Depends(require_auth)):
    """Digest de cobranças pro app (sem push). Mesmo cálculo do /internal/run-digest."""
    return await tasks.run_digest()


@app.post("/internal/notify")
async def internal_notify(body: NotifyIn, x_internal_token: str = Header(default="")):
    if x_internal_token != settings.internal_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "token interno inválido")
    return await push.send_push(store.list_devices(), body.title, body.body)


@app.post("/internal/run-digest")
async def internal_run_digest(x_internal_token: str = Header(default="")):
    """Calcula o digest de cobranças (regras do cutuca) e faz push. Caminho dev/mock/
    fallback; em produção o cron do Hermes calcula e usa /internal/notify (D-14)."""
    if x_internal_token != settings.internal_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "token interno inválido")
    d = await tasks.run_digest()
    sent = 0
    if d["count"] > 0:
        res = await push.send_push(
            store.list_devices(), f"🔔 {d['count']} cobranças de hoje", d["body"]
        )
        sent = res["sent"]
    return {"count": d["count"], "pushed": sent, "text": d["text"], "tasks": d["tasks"]}
