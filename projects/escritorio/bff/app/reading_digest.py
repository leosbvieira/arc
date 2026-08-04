"""Digest canônico do snapshot fonte de uma sessão de leitura."""

import hashlib


def _put(hasher, value: str | int | None) -> None:
    if value is None:
        payload = b"N"
    elif isinstance(value, int) and not isinstance(value, bool):
        payload = b"I" + str(value).encode("ascii")
    elif isinstance(value, str):
        payload = b"S" + value.encode("utf-8")
    else:
        raise TypeError("reading_digest_tipo_invalido")
    hasher.update(len(payload).to_bytes(8, "big"))
    hasher.update(payload)


def source_digest(
    *,
    client_key: str,
    livro: str,
    pagina_inicial: int | None,
    pagina_final: int | None,
    chunks: list[dict],
) -> str:
    """SHA-256 length-prefixed; texto entra em UTF-8 sem normalização ou limpeza."""
    ordered = sorted(chunks, key=lambda chunk: int(chunk["seq"]))
    hasher = hashlib.sha256()
    _put(hasher, "reading-source-v1")
    _put(hasher, client_key)
    _put(hasher, livro)
    _put(hasher, pagina_inicial)
    _put(hasher, pagina_final)
    _put(hasher, len(ordered))
    for chunk in ordered:
        _put(hasher, int(chunk["seq"]))
        _put(hasher, chunk["hook"])
        _put(hasher, chunk["texto"])
    return hasher.hexdigest()
