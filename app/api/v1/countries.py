from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from typing import Any, Dict, List
from uuid import uuid4
from datetime import datetime
from app.services.country_service import country_summary_with_fact
from app.services.llm_client import cultural_fact, country_details  # added

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

    try:
        if method == "message/send":
            msg = params.get("message") or {}
            parts = msg.get("parts") or []
            user_text = _extract_text_from_parts(parts)
            if not user_text:
                raise ValueError("No text content found in message parts.")

            intent = parse_intent(user_text)
            if intent["cmd"] != "on_demand":
                text = "Use chat commands: /subscribe HH:MM [country] or /unsubscribe"
            else:
                text = await country_summary_with_fact(intent["country"])

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

            intent = parse_intent(user_text)
            if intent["cmd"] != "on_demand":
                text = "Use chat commands: /subscribe HH:MM [country] or /unsubscribe"
            else:
                text = await country_summary_with_fact(intent["country"])

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
