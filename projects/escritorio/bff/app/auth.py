import hmac
import time

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

_bearer = HTTPBearer(auto_error=False)

# Um JWT do app tem ~150 bytes. Qualquer coisa perto de 8 KiB não é um token: é
# alguém testando o parser. Cortar antes do decode evita gastar CPU com lixo.
_TOKEN_MAX_BYTES = 8192


def secret_equal(provided: str | None, expected: str | None) -> bool:
    """Comparação em tempo constante de segredos (token interno, etc.).

    Vazio de qualquer lado é SEMPRE falso: um `.env` sem `INTERNAL_TOKEN` não pode
    virar "qualquer header vazio passa". Compara em BYTES porque `compare_digest`
    recusa `str` não-ASCII com TypeError (lição do login com senha acentuada).
    """
    if not provided or not expected:
        return False
    try:
        return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))
    except UnicodeError:
        return False


def make_token() -> str:
    now = int(time.time())
    payload = {"sub": "owner", "iat": now, "exp": now + settings.jwt_ttl_hours * 3600}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def require_auth(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if cred is None or len(cred.credentials) > _TOKEN_MAX_BYTES:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sem token")
    try:
        # `require`: um token assinado com o segredo certo mas SEM `exp` era aceito
        # para sempre pelo decode padrão. Aqui só vale o formato que `make_token` emite.
        payload = jwt.decode(
            cred.credentials,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido")
    if payload.get("sub") != "owner":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido")
    return "owner"
