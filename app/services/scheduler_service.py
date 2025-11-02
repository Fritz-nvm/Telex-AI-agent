import json
from pathlib import Path
from typing import Dict, Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.config import settings
from app.services.country_service import country_summary_with_fact
from app.services.telex_client import send_message

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "subscriptions.json"
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)
    return _scheduler


def _read_json_with_comments(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"subscriptions": []}
    try:
        # Strip lines that start with // to support a top-of-file comment
        lines = [
            ln
            for ln in path.read_text().splitlines()
            if not ln.strip().startswith("//")
        ]
        return json.loads("\n".join(lines)) if lines else {"subscriptions": []}
    except Exception:
        return {"subscriptions": []}


def _write_json(path: Path, data: Dict[str, Any]):
    path.write_text(json.dumps(data, indent=2))


def _load_subscriptions() -> Dict[str, Any]:
    return _read_json_with_comments(DATA_PATH)


def _save_subscriptions(data: Dict[str, Any]):
    _write_json(DATA_PATH, data)


def _job_id(channel_id: str) -> str:
    return f"daily-fact-{channel_id}"


async def _send_daily_fact(channel_id: str, country: Optional[str]):
    target = country or "a random country"
    text = await country_summary_with_fact(target)
    await send_message(channel_id, text)


def register_job(
    channel_id: str, hour: int, minute: int, country: Optional[str] = None
):
    sched = get_scheduler()
    jid = _job_id(channel_id)
    try:
        existing = sched.get_job(jid)
        if existing:
            sched.remove_job(jid)
    except Exception:
        pass
    trigger = CronTrigger(hour=hour, minute=minute)
    sched.add_job(
        _send_daily_fact,
        trigger,
        id=jid,
        kwargs={"channel_id": channel_id, "country": country},
        replace_existing=True,
    )


def subscribe(channel_id: str, time_hhmm: str, country: Optional[str] = None):
    data = _load_subscriptions()
    subs = [
        s for s in data.get("subscriptions", []) if s.get("channel_id") != channel_id
    ]
    hh, mm = time_hhmm.split(":")
    subs.append({"channel_id": channel_id, "time": time_hhmm, "country": country})
    data["subscriptions"] = subs
    _save_subscriptions(data)
    register_job(channel_id, int(hh), int(mm), country)


def unsubscribe(channel_id: str):
    data = _load_subscriptions()
    subs = [
        s for s in data.get("subscriptions", []) if s.get("channel_id") != channel_id
    ]
    data["subscriptions"] = subs
    _save_subscriptions(data)
    sched = get_scheduler()
    try:
        sched.remove_job(_job_id(channel_id))
    except Exception:
        pass


def load_all_jobs_on_startup():
    data = _load_subscriptions()
    for s in data.get("subscriptions", []):
        time_hhmm = s.get("time", "09:00")
        hh, mm = time_hhmm.split(":")
        register_job(s["channel_id"], int(hh), int(mm), s.get("country"))
