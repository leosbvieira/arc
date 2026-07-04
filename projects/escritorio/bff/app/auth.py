import time

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

_bearer = HTTPBearer(auto_error=False)


def make_token() -> str:
    now = int(time.time())
    payload = {"sub": "owner", "iat": now, "exp": now + settings.jwt_ttl_hours * 3600}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def require_auth(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sem token")
    try:
        payload = jwt.decode(
            cred.credentials, settings.jwt_secret, algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token inválido")
    return str(payload.get("sub", "owner"))
