import httpx

from .config import settings


async def capture(text: str, profile: str | None = None) -> str:
    """Manda o texto pro Hermes (profile) e devolve a resposta.

    Em mock (default) responde sem rede — pra rodar o L0 sem o VPS/Hermes.
    Quando o Hermes estiver de pé: HERMES_MOCK=false + URL + chave.
    Endpoint assumido = OpenAI-compatible /v1/chat/completions; confirmar
    contra os docs do Hermes ao ligar de verdade.
    """
    prof = profile or settings.hermes_profile_capture

    if settings.hermes_mock or not settings.hermes_api_key:
        return f"[mock:{prof}] anotado: {text}"

    url = f"{settings.hermes_base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {settings.hermes_api_key}"}
    payload = {"model": prof, "messages": [{"role": "user", "content": text}]}

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"]
