from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.schemas.telex import TelexMessage
from app.services.country_service import country_summary_with_fact
from app.services.telex_client import send_message
from app.services.scheduler_service import subscribe, unsubscribe

router = APIRouter()


def parse_intent(text: str):
    """
    Supported:
    - 'tell me about <country>'
    - '<country>'
    - '/subscribe HH:MM [country]'
    - '/unsubscribe'
    """
    t = (text or "").strip()
    low = t.lower()
    if low.startswith("/unsubscribe"):
        return {"cmd": "unsubscribe"}
    if low.startswith("/subscribe"):
        parts = t.split()
        if len(parts) >= 2 and ":" in parts[1]:
            time_hhmm = parts[1]
            country = " ".join(parts[2:]) if len(parts) > 2 else None
            return {"cmd": "subscribe", "time": time_hhmm, "country": country}
        raise ValueError("Usage: /subscribe HH:MM [country]")
    if low.startswith("tell me about "):
        return {"cmd": "on_demand", "country": t[15:].strip()}
    # fallback: treat as country name
    return {"cmd": "on_demand", "country": t}


async def handle_on_demand(channel_id: str, country: str):
    text = await country_summary_with_fact(country)
    await send_message(channel_id, text)


@router.post("/webhook", status_code=202)
async def telex_webhook(payload: TelexMessage, background_tasks: BackgroundTasks):
    if not payload.text:
        raise HTTPException(status_code=400, detail="Empty message text")
    try:
        intent = parse_intent(payload.text)
    except ValueError as ve:
        background_tasks.add_task(send_message, payload.channel_id, str(ve))
        return {"status": "accepted"}

    cmd = intent["cmd"]
    if cmd == "unsubscribe":
        unsubscribe(payload.channel_id)
        background_tasks.add_task(
            send_message, payload.channel_id, "Unsubscribed from daily country facts."
        )
    elif cmd == "subscribe":
        subscribe(payload.channel_id, intent["time"], intent.get("country"))
        msg = f"Subscribed to daily facts at {intent['time']} UTC"
        if intent.get("country"):
            msg += f" about {intent['country']}."
        else:
            msg += "."
        background_tasks.add_task(send_message, payload.channel_id, msg)
    else:
        background_tasks.add_task(
            handle_on_demand, payload.channel_id, intent["country"]
        )
    return {"status": "accepted"}


@router.get("/health")
async def health():
    return {"ok": True}
