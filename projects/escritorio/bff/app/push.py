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


# O recibo é a única fonte que diz se o push CHEGOU. O ticket só confirma que a Expo
# aceitou a mensagem — e é no recibo que ela reporta `DeviceNotRegistered`.
RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"


async def get_receipts(ticket_ids: list[str]) -> dict:
    """{ticket_id: recibo}. Lote de 300 é o limite documentado da Expo."""
    if not ticket_ids:
        return {}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            RECEIPTS_URL,
            json={"ids": ticket_ids[:300]},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        result = resp.json()

    dados = result.get("data")
    return dados if isinstance(dados, dict) else {}
