import httpx
from app.core.config import settings


def _headers():
    return {
        "Authorization": f"Bearer {settings.TELEX_BOT_TOKEN}",
        "Content-Type": "application/json",
    }


def _send_url():
    return f"{settings.TELEX_API_BASE_URL.rstrip('/')}/{settings.TELEX_A2A_SEND_PATH.lstrip('/')}"


async def send_message(channel_id: str, text: str):
    payload = {
        "type": "message",
        "channel_id": channel_id,
        "text": text,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.post(_send_url(), headers=_headers(), json=payload)
            r.raise_for_status()
            print(f"[TELEX] Sent to {channel_id}")
        except httpx.HTTPStatusError as e:
            print(f"[TELEX ERROR] {e.response.status_code} {e.response.text}")
        except Exception as e:
            print(f"[TELEX ERROR] {e}")
