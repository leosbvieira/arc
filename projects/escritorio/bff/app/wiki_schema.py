"""Normaliza o JSON Schema do Pydantic para o dialeto plano que o app valida.

O `model_json_schema()` v2 emite `$defs`/`$ref` para submodelos e
`anyOf: [X, {type: "null"}]` para opcionais. O caminhador do app implementa só
`type`, `properties`, `required`, `items`, `minItems`, `enum` e `nullable`.
Sem esta etapa, regenerar o contrato quebraria o próprio teste, sempre.
"""
import json

PALAVRAS = {"type", "properties", "required", "items", "minItems", "enum", "nullable"}


def _normalizar(no: dict, defs: dict) -> dict:
    if "$ref" in no:
        nome = no["$ref"].rsplit("/", 1)[-1]
        return _normalizar(dict(defs[nome]), defs)

    if "anyOf" in no:
        ramos = [r for r in no["anyOf"] if r.get("type") != "null"]
        anulavel = len(ramos) != len(no["anyOf"])
        if len(ramos) != 1:
            raise ValueError(f"anyOf com {len(ramos)} ramos não-nulos: {no['anyOf']}")
        saida = _normalizar(dict(ramos[0]), defs)
        if anulavel:
            saida["nullable"] = True
        return saida

    saida = {}
    for chave, valor in no.items():
        if chave in ("title", "description", "default"):
            continue
        if chave == "const":
            saida["enum"] = [valor]
        elif chave == "properties":
            saida["properties"] = {k: _normalizar(dict(v), defs) for k, v in valor.items()}
        elif chave == "items":
            saida["items"] = _normalizar(dict(valor), defs)
        else:
            saida[chave] = valor
    return saida


def schema_normalizado() -> dict:
    from .main import ParametrosOut

    bruto = ParametrosOut.model_json_schema()
    defs = bruto.pop("$defs", {})
    return _normalizar(bruto, defs)


if __name__ == "__main__":
    print(json.dumps(schema_normalizado(), indent=2, ensure_ascii=False, sort_keys=True))
