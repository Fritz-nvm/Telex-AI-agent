from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime
import re
import json
import asyncio
import httpx
import traceback

from app.services.llm_client import cultural_fact, country_details
from app.schemas.telex import (
    JSONRPCRequest,
    JSONRPCResponse,
    TelexMessage,
    TaskResult,
    Configuration,
    MessagePart,
)

router = APIRouter()

# Multi-word countries
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
    "cote d'ivoire",
    "côte d'ivoire",
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
    """Remove HTML tags, braces, normalize whitespace."""
    t = re.sub(r"[{}]", " ", t or "")
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def extract_country(text: str) -> str:
    """
    Extract country name from potentially noisy input.
    Prioritizes explicit phrases like "tell me about X".
    """
    s = _clean_text(text).lower()

    # Try explicit patterns first
    patterns = [
        r"(?:tell me about|fact about|about)\s+([a-z][a-z\s''\-]+?)(?:\s+tell|\s+fact|\s*$)",
        r"(?:tell me about|fact about|about)\s+([a-z][a-z\s''\-]+)[\.\!\?]",
    ]

    for pat in patterns:
        m = re.search(pat, s)
        if m:
            candidate = m.group(1).strip(" .!?,;:")
            return candidate.title()

    # Token-based extraction
    tokens = re.findall(r"[a-z][a-z''\-]+", s)
    if not tokens:
        return ""

    # Check last two tokens for multi-word countries
    if len(tokens) >= 2:
        last_two = f"{tokens[-2]} {tokens[-1]}"
        if last_two in MULTI_WORD_COUNTRIES:
            return last_two.title()

    # Scan for any multi-word match
    joined = " ".join(tokens)
    last_hit = None

    for mw in MULTI_WORD_COUNTRIES:
        idx = joined.rfind(mw)
        if idx != -1 and (last_hit is None or idx > last_hit[0]):
            last_hit = (idx, mw)

    if last_hit:
        return last_hit[1].title()

    # Fallback to last token
    return tokens[-1].title()


def format_country_response(details: Optional[Dict[str, Any]], fact: str) -> str:
    """Format country details and fact into readable text."""
    if not details:
        return fact

    name = details.get("name", "Unknown")
    capital = ", ".join(details.get("capital", [])) or "N/A"
    region = details.get("region", "N/A")
    subregion = details.get("subregion", "N/A")

    pop = details.get("population_estimate")
    population = f"{pop:,}" if isinstance(pop, int) else "N/A"

    languages = ", ".join(details.get("languages", [])) or "N/A"
    currencies = ", ".join(details.get("currencies", [])) or "N/A"
    timezones = ", ".join(details.get("timezones", [])) or "N/A"

    code = details.get("cca2") or details.get("cca3") or ""
    code_display = f" [{code}]" if code else ""

    return f"""{name}{code_display}
- Capital: {capital}
- Region: {region} ({subregion})
- Population: {population}
- Languages: {languages}
- Currencies: {currencies}
- Timezones: {timezones}

Cultural fact: {fact}"""


async def country_summary_with_fact(country_name: str) -> str:
    """Main processing logic with error handling."""
    try:
        # Parallel requests for speed
        details_task = country_details(country_name)
        fact_task = cultural_fact(country_name)

        details, fact = await asyncio.gather(
            details_task, fact_task, return_exceptions=True
        )

        # Handle partial failures
        if isinstance(details, Exception):
            print(f"[ERROR] Details fetch failed: {details}")
            details = None

        if isinstance(fact, Exception):
            print(f"[ERROR] Fact fetch failed: {fact}")
            fact = "Cultural fact unavailable at this time."

        return format_country_response(details, fact)

    except Exception as e:
        print(f"[ERROR] country_summary_with_fact: {traceback.format_exc()}")
        return f"Sorry, I encountered an error processing information about {country_name}."


def _make_agent_message(task_id: str, text: str) -> Dict[str, Any]:
    """Create a valid Telex agent message."""
    return {
        "kind": "message",
        "role": "agent",
        "parts": [{"kind": "text", "text": text}],
        "messageId": str(uuid4()),
        "taskId": task_id,
    }


async def push_to_telex(push_cfg: Dict[str, Any], agent_msg: Dict[str, Any]) -> bool:
    """Push final result to Telex webhook (for non-blocking mode)."""
    url = push_cfg.get("url")
    token = push_cfg.get("token")

    if not url or not token:
        print("[PUSH] Missing push config")
        return False

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {"message": agent_msg}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            print(f"[PUSH] Success: {response.status_code}")
            return True
    except Exception as e:
        print(f"[PUSH] Failed: {traceback.format_exc()}")
        return False


async def process_and_push(
    user_text: str,
    task_id: str,
    context_id: str,
    push_cfg: Dict[str, Any],
    original_msg: Dict[str, Any],
):
    """Background task to process request and push result."""
    try:
        # Extract country
        country = extract_country(user_text)
        if not country:
            result_text = "Please specify a country name (e.g., 'tell me about Kenya')."
        else:
            # Process with timeout
            result_text = await asyncio.wait_for(
                country_summary_with_fact(country), timeout=25.0
            )
    except asyncio.TimeoutError:
        result_text = "Sorry, the request took too long. Please try again."
    except Exception as e:
        print(f"[PROCESS] Error: {traceback.format_exc()}")
        result_text = f"Sorry, I encountered an error: {str(e)}"

    # Create agent message
    agent_msg = _make_agent_message(task_id, result_text)

    # Push to Telex
    await push_to_telex(push_cfg, agent_msg)


@router.post("/a2a/messsage", response_class=PlainTextResponse)
async def a2a_text(body: Dict[str, Any], request: Request):
    """
    Simple HTTP A2A endpoint (blocking only).
    Accepts: {"text": "tell me about Kenya"}
    Returns: Plain text response
    """
    trace_id = request.headers.get("X-Telex-Trace-Id", "unknown")
    print(f"[A2A/TEXT] trace={trace_id} in")

    txt = (body.get("text") or "").strip()

    if not txt:
        return "Please provide a country name (e.g., 'tell me about Japan')."

    try:
        country = extract_country(txt)
        if not country:
            return "Please specify a country (e.g., 'tell me about Japan')."

        # Timeout protection
        result = await asyncio.wait_for(
            country_summary_with_fact(country), timeout=25.0
        )

        print(f"[A2A/TEXT] trace={trace_id} out len={len(result)}")
        return result

    except asyncio.TimeoutError:
        return "Sorry, that took too long. Please try again."
    except Exception as e:
        print(f"[A2A/TEXT] trace={trace_id} error: {traceback.format_exc()}")
        return f"Sorry, I encountered an error: {str(e)}"


@router.post("/a2a/country_info")
async def a2a_country(request: Request):
    """
    JSON-RPC A2A endpoint supporting both blocking and non-blocking modes.
    """
    trace_id = request.headers.get("X-Telex-Trace-Id", "unknown")

    # Parse request
    try:
        body = await request.json()
    except json.JSONDecodeError as e:
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error",
                    "data": {"details": str(e)},
                },
            },
        )

    print(f"[A2A/COUNTRY] trace={trace_id} method={body.get('method')}")

    # Validate JSON-RPC structure
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

    # Extract configuration
    config = params.get("configuration") or {}
    blocking = bool(config.get("blocking", True))
    push_cfg = config.get("pushNotificationConfig") or {}

    print(f"[A2A/COUNTRY] blocking={blocking}")

    try:
        if method == "message/send":
            msg = params.get("message")
            if not msg:
                raise ValueError("Missing 'message' in params")

            # Extract user text from message parts
            parts = msg.get("parts") or []
            user_text = ""

            for part in parts:
                if part.get("kind") == "text" and part.get("text"):
                    user_text = part["text"].strip()
                    break

            if not user_text:
                raise ValueError("No text content found in message parts")

            task_id = msg.get("taskId") or str(uuid4())
            context_id = params.get("contextId") or str(uuid4())

            # NON-BLOCKING MODE: Return immediately and process async
            if not blocking:
                # Start background processing
                asyncio.create_task(
                    process_and_push(user_text, task_id, context_id, push_cfg, msg)
                )

                # Return pending status immediately
                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "id": task_id,
                            "contextId": context_id,
                            "status": {
                                "state": "running",
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                            "artifacts": [],
                            "history": [],
                            "kind": "task",
                        },
                    }
                )

            # BLOCKING MODE: Process and return result
            country = extract_country(user_text)
            if not country:
                result_text = "Please specify a country (e.g., 'tell me about Kenya')."
            else:
                try:
                    result_text = await asyncio.wait_for(
                        country_summary_with_fact(country), timeout=25.0
                    )
                except asyncio.TimeoutError:
                    result_text = "Sorry, that took too long. Please try again."

            agent_msg = _make_agent_message(task_id, result_text)

            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "id": task_id,
                        "contextId": context_id,
                        "status": {
                            "state": "completed",
                            "timestamp": datetime.utcnow().isoformat(),
                            "message": agent_msg,
                        },
                        "artifacts": [],
                        "history": [msg, agent_msg],
                        "kind": "task",
                    },
                }
            )

        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                    "data": {"supported_methods": ["message/send"]},
                },
            }
        )

    except ValueError as ve:
        print(f"[A2A/COUNTRY] Validation error: {ve}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32602,
                    "message": "Invalid params",
                    "data": {"details": str(ve)},
                },
            }
        )
    except Exception as e:
        print(f"[A2A/COUNTRY] Internal error: {traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": {"details": str(e)},
                },
            },
        )


@router.get("/country")
async def get_country_info(name: str):
    """Debug endpoint for quick testing."""
    try:
        country = extract_country(name)
        if not country:
            raise HTTPException(status_code=400, detail="Invalid country name")

        result = await asyncio.wait_for(
            country_summary_with_fact(country), timeout=25.0
        )

        return {"country": country, "info": result}

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Request timeout")
    except Exception as e:
        print(f"[GET/COUNTRY] Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Atlas Country Agent",
        "timestamp": datetime.utcnow().isoformat(),
    }
