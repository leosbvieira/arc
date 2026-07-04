import httpx

from .config import settings


async def send_push(
    tokens: list[str], title: str, body: str, data: dict | None = None
) -> dict:
    """Fan-out via Expo Push Service (a Expo/EAS gerencia o FCM por baixo)."""
    if not tokens:
        return {"sent": 0, "tickets": []}

    messages = [
        {
            "to": t,
            "title": title,
            "body": body,
            "sound": "default",
            "data": data or {},
        }
        for t in tokens
    ]

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            settings.expo_push_url,
            json=messages,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        result = resp.json()

    return {"sent": len(messages), "tickets": result.get("data", [])}
