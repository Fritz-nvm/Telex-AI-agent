from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from typing import Any, Dict, List, Tuple
from uuid import uuid4
from datetime import datetime
import re
import json
import asyncio

from app.services.llm_client import cultural_fact, country_details

router = APIRouter()


def parse_intent(text: str):
    """
    Supported:
    - 'tell me about <country>'
    - '<country>'
    - '/subscribe HH:MM [country]'  (guided response only; push scheduling removed)
    - '/unsubscribe'                (guided response only)
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
    return {"cmd": "on_demand", "country": t}


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _extract_text_from_parts(parts: List[Dict[str, Any]]) -> str:
    for p in parts or []:
        if p.get("kind") == "text" and p.get("text"):
            return p["text"].strip()
    return ""


def _make_agent_message(task_id: str, text: str) -> Dict[str, Any]:
    return {
        "kind": "message",
        "role": "agent",
        "parts": [{"kind": "text", "text": text}],
        "messageId": str(uuid4()),
        "taskId": task_id,
    }


def _as_list(v) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x]
    if isinstance(v, str):
        return [v] if v else []
    if isinstance(v, dict):
        return [str(x) for x in v.values() if x]
    return []


# --- New country extraction helpers ---

MULTI_WORD_COUNTRIES = {
    "south africa",
    "saudi arabia",
    "new zealand",
    "united kingdom",
    "united states",
    "costa rica",
    "czech republic",
    "dominican republic",
    "ivory coast",
    "cote d’ivoire",
    "côte d’ivoire",
    "papua new guinea",
    "trinidad and tobago",
    "bosnia and herzegovina",
    "north macedonia",
    "united arab emirates",
    "sri lanka",
    "south korea",
    "north korea",
    "hong kong",
    "sierra leone",
    "vatican city",
    "el salvador",
}


def _clean_text(t: str) -> str:
    # Drop braces payloads and HTML tags that sometimes leak in
    t = re.sub(r"[{}]", " ", t or "")
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _extract_country_from_text(t: str) -> str:
    """
    Heuristics:
    1) Explicit phrases: 'tell me about X', 'about X', 'fact about X'
    2) Else, pick the last country-like mention; prefer known multi-word names.
    """
    s = _clean_text(t).lower()

    # 1) Explicit phrase capture
    patterns = [
        r"(?:tell me about|fact about|about)\s+([a-z][a-z\s'’\-]+)$",
        r"(?:tell me about|fact about|about)\s+([a-z][a-z\s'’\-]+)[\.\!\?]",
    ]
    for pat in patterns:
        m = re.search(pat, s)
        if m:
            cand = m.group(1).strip(" .!?,;:")
            return cand.title()

    # 2) Token scan; choose the last plausible country mention
    tokens = re.findall(r"[a-z][a-z'’\-]+", s)
    if not tokens:
        return ""

    # Try last two-token window first (handles 'south africa', etc.)
    if len(tokens) >= 2:
        last2 = f"{tokens[-2]} {tokens[-1]}"
        if last2 in MULTI_WORD_COUNTRIES:
            return last2.title()

    # Scan for any multi-word match ending nearest the end
    joined = " ".join(tokens)
    last_hit: Tuple[int, str] | None = None
    for mw in MULTI_WORD_COUNTRIES:
        idx = joined.rfind(mw)
        if idx != -1 and (last_hit is None or idx > last_hit[0]):
            last_hit = (idx, mw)
    if last_hit:
        return last_hit[1].title()

    # Fallback: last single token (e.g., "Kenya", "Japan")
    return tokens[-1].title()


# --- End extraction helpers ---


def _normalize_country_input(text: str) -> str:
    """
    Handles noisy inputs like 'kenya japan japan ...'.
    If any token repeats, pick the most frequent token; else keep original text
    to allow multi-word countries (e.g., 'United States').
    """
    t = (text or "").strip()
    if not t:
        return t
    tokens = re.findall(r"[A-Za-z][A-Za-z\-'’]+", t)
    if not tokens:
        return t
    freq: Dict[str, int] = {}
    for tok in tokens:
        k = tok.strip("'’").lower()
        freq[k] = freq.get(k, 0) + 1
    if not freq:
        return t
    most_common = max(freq.values())
    if most_common > 1:
        candidate = max(freq.items(), key=lambda kv: kv[1])[0]
        return candidate[:1].upper() + candidate[1:]
    return t


def format_details_and_fact(details: Dict[str, Any] | None, fact: str) -> str:
    if not details:
        return fact

    name = details.get("name") or "Unknown country"
    capital = ", ".join(_as_list(details.get("capital"))) or "N/A"
    region = details.get("region") or "N/A"
    subregion = details.get("subregion") or "N/A"
    pop = details.get("population_estimate")
    population_s = (
        f"{pop:,}"
        if isinstance(pop, int)
        else ("N/A" if pop in (None, "", "null") else str(pop))
    )
    languages_s = ", ".join(_as_list(details.get("languages"))) or "N/A"
    currencies_s = ", ".join(_as_list(details.get("currencies"))) or "N/A"
    timezones_s = ", ".join(_as_list(details.get("timezones"))) or "N/A"
    cca2 = details.get("cca2") or ""
    cca3 = details.get("cca3") or ""

    fact_line = fact
    low = fact.lower()
    if (
        ("invalid api key" in low)
        or ("llm not available" in low)
        or low.startswith("server not configured")
        or low.startswith("sorry")
    ):
        fact_line = "N/A (LLM unavailable)"

    code = (cca2 or cca3 or "").strip()
    code_disp = f" [{code}]" if code else ""

    return (
        f"{name}{code_disp}\n"
        f"- Capital: {capital}\n"
        f"- Region: {region} ({subregion})\n"
        f"- Population: {population_s}\n"
        f"- Languages: {languages_s}\n"
        f"- Currencies: {currencies_s}\n"
        f"- Timezones: {timezones_s}\n"
        f"\nCulture fact: {fact_line}"
    )


async def country_summary_with_fact(country: str) -> str:
    # NEW: robust extraction for the chosen country from noisy text
    chosen = _extract_country_from_text(country)
    if not chosen:
        return "Please specify a country (e.g., 'tell me about Japan')."
    details = await country_details(chosen)
    fact = await cultural_fact(chosen)
    return format_details_and_fact(details, fact)


# A2A: JSON-RPC endpoint (use in Telex workflow generic A2A node)
@router.post("/a2a/country")
async def a2a_country(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            },
        )

    # Log minimal info to Railway logs
    try:
        print(
            "[A2A] incoming:",
            json.dumps({"id": body.get("id"), "method": body.get("method")}),
        )
    except Exception:
        pass

    req_id = body.get("id")
    if body.get("jsonrpc") != "2.0" or req_id is None:
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32600, "message": "Invalid Request"},
            },
        )

    method = body.get("method")
    params = body.get("params", {}) or {}

    async def handle_text(user_text: str) -> str:
        intent = parse_intent(user_text)
        if intent["cmd"] != "on_demand":
            return "Use chat commands: /subscribe HH:MM [country] or /unsubscribe"
        # Make sure we don’t exceed Telex node timeout
        try:
            return await asyncio.wait_for(
                country_summary_with_fact(intent["country"]), timeout=20
            )
        except asyncio.TimeoutError:
            return "Sorry, that took too long. Please try again."

    try:
        if method == "message/send":
            msg = params.get("message") or {}
            parts = msg.get("parts") or []
            user_text = _extract_text_from_parts(parts)
            if not user_text:
                raise ValueError("No text content found in message parts.")

            text = await handle_text(user_text)
            context_id = params.get("contextId") or str(uuid4())
            task_id = msg.get("taskId") or str(uuid4())
            agent_msg = _make_agent_message(task_id, text)

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "id": task_id,
                    "contextId": context_id,
                    "status": {
                        "state": "completed",
                        "timestamp": _now_iso(),
                        "message": agent_msg,
                    },
                    "artifacts": [],
                    "history": [msg, agent_msg],
                    "kind": "task",
                },
            }

        elif method == "execute":
            messages = params.get("messages") or []
            if not messages:
                raise ValueError("No messages provided.")
            last = messages[-1]
            user_text = _extract_text_from_parts(last.get("parts") or [])
            if not user_text:
                raise ValueError("No text content found in message parts.")

            text = await handle_text(user_text)
            context_id = params.get("contextId") or str(uuid4())
            task_id = params.get("taskId") or str(uuid4())
            agent_msg = _make_agent_message(task_id, text)
            history = messages + [agent_msg]

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "id": task_id,
                    "contextId": context_id,
                    "status": {
                        "state": "completed",
                        "timestamp": _now_iso(),
                        "message": agent_msg,
                    },
                    "artifacts": [],
                    "history": history,
                    "kind": "task",
                },
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": "Method not found"},
            }
    except ValueError as ve:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32602,
                "message": "Invalid params",
                "data": {"details": str(ve)},
            },
        }
    except Exception as e:
        print("[A2A] error:", repr(e))
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": {"details": str(e)},
            },
        }


# A2A: simple HTTP endpoints (use in HTTP/A2A skill if preferred)
@router.post("/a2a/text", response_class=PlainTextResponse)
async def a2a_text(body: Dict[str, Any]):
    txt = (body.get("text") or "").strip()
    if not txt:
        return "Query param 'text' is required."
    intent = parse_intent(txt)
    if intent["cmd"] != "on_demand":
        return "Use chat commands: /subscribe HH:MM [country] or /unsubscribe"
    return await country_summary_with_fact(intent["country"])


@router.post("/a2a/json")
async def a2a_json(body: Dict[str, Any]):
    txt = (body.get("text") or "").strip()
    if not txt:
        return {
            "messages": [{"type": "message", "text": "Query param 'text' is required."}]
        }
    intent = parse_intent(txt)
    if intent["cmd"] != "on_demand":
        return {
            "messages": [
                {
                    "type": "message",
                    "text": "Use /subscribe HH:MM [country] or /unsubscribe",
                }
            ]
        }
    result = await country_summary_with_fact(intent["country"])
    return {"messages": [{"type": "message", "text": result}]}


# New: structured details via Groq (debug/helper)
@router.post("/a2a/details")
async def a2a_details(body: Dict[str, Any]):
    txt = (body.get("text") or "").strip()
    if not txt:
        return {"error": "Query param 'text' is required."}
    det = await country_details(txt)
    if not det:
        return {"details": None, "message": "LLM unavailable or country not resolved."}
    return {"details": det}


# Quick test endpoints
@router.get("/country")
async def country(name: str):
    text = await country_summary_with_fact(name)
    return {"text": text}


# LLM health check
@router.get("/llm-fact")
async def llm_fact(country: str):
    c = (country or "").strip()
    if not c:
        raise HTTPException(status_code=400, detail="Query param 'country' is required")
    fact = await cultural_fact(c)
    return {"country": c, "fact": fact}


@router.get("/health")
async def health():
    return {"ok": True}
