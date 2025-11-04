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
from pydantic import ValidationError

from app.services.llm_client import cultural_fact, country_details
from app.schemas.telex import (
    JSONRPCRequest,
    JSONRPCResponse,
    TelexMessage,
    TaskResult,
    TaskStatus,
    Configuration,
    MessagePart,
    PushNotificationConfig,
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
    Returns the LAST country mentioned in the text.
    """
    s = _clean_text(text).lower()

    # Try explicit patterns first (these take precedence)
    patterns = [
        r"(?:tell me about|fact about|about|information on)\s+([a-z][a-z\s''\-]+?)(?:\s+tell|\s+fact|\s+information|\s*$)",
        r"(?:tell me about|fact about|about|information on)\s+([a-z][a-z\s''\-]+)[\.\!\?]",
    ]

    # Find ALL matches with explicit patterns
    explicit_matches = []
    for pat in patterns:
        for m in re.finditer(pat, s):
            candidate = m.group(1).strip(" .!?,;:")
            explicit_matches.append(candidate)

    # If we found explicit mentions, return the LAST one
    if explicit_matches:
        last_match = explicit_matches[-1]
        # Check if it's a multi-word country
        if last_match in MULTI_WORD_COUNTRIES:
            return last_match.title()
        # Otherwise take first word from the match
        first_word = last_match.split()[0]
        return first_word.title()

    # Token-based extraction - scan from RIGHT to LEFT
    tokens = re.findall(r"[a-z][a-z''\-]+", s)
    if not tokens:
        return ""

    # Check last two tokens for multi-word countries
    if len(tokens) >= 2:
        last_two = f"{tokens[-2]} {tokens[-1]}"
        if last_two in MULTI_WORD_COUNTRIES:
            return last_two.title()

    # Scan backwards for any multi-word match
    for i in range(len(tokens) - 2, -1, -1):
        two_words = f"{tokens[i]} {tokens[i+1]}"
        if two_words in MULTI_WORD_COUNTRIES:
            return two_words.title()

    # Return last token as country
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


def _make_agent_message(task_id: str, text: str) -> dict:
    """Create a simple agent message dict matching successful examples."""
    return {
        "kind": "message",
        "role": "agent",
        "parts": [{"kind": "text", "text": text}],
        "messageId": str(uuid4()),
        "taskId": task_id,
    }


def _make_user_message(user_text: str, original_message_id: str) -> dict:
    """Create a simple user message dict for history."""
    return {
        "kind": "message",
        "role": "user",
        "parts": [{"kind": "text", "text": user_text}],
        "messageId": original_message_id,
    }


@router.post("/a2a/message", response_class=PlainTextResponse)
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
        print(f"[A2A/TEXT] Extracted country: '{country}'")

        if not country:
            return "Please specify a country (e.g., 'tell me about Japan')."

        # Timeout protection
        result = await asyncio.wait_for(
            country_summary_with_fact(country), timeout=25.0
        )

        print(f"[A2A/TEXT] trace={trace_id} out len={len(result)}")
        return result

    except asyncio.TimeoutError:
        print(f"[A2A/TEXT] trace={trace_id} timeout")
        return "Sorry, that took too long. Please try again."
    except Exception as e:
        print(f"[A2A/TEXT] trace={trace_id} error: {traceback.format_exc()}")
        return f"Sorry, I encountered an error: {str(e)}"


@router.post("/a2a/country_info")
async def a2a_country(request: Request):
    """
    JSON-RPC A2A endpoint - FORCE BLOCKING MODE to avoid validation issues.
    """
    trace_id = request.headers.get("X-Telex-Trace-Id", "unknown")

    # Parse request
    try:
        body = await request.json()
        print(f"[A2A/COUNTRY] Received request for method: {body.get('method')}")
    except json.JSONDecodeError as e:
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            },
        )

    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})

    # FORCE BLOCKING MODE to avoid validation issues
    blocking = True  # Always use blocking mode

    try:
        if method == "message/send":
            msg_data = params.get("message", {})

            # Extract user text from message parts
            user_text = ""
            for part in msg_data.get("parts", []):
                if part.get("kind") == "text" and part.get("text"):
                    user_text = part["text"].strip()
                    break

            if not user_text:
                raise ValueError("No text content found in message parts")

            task_id = msg_data.get("taskId") or str(uuid4())
            context_id = params.get("contextId") or str(uuid4())
            original_message_id = msg_data.get("messageId")

            print(f"[A2A/COUNTRY] Processing in BLOCKING mode: '{user_text[:50]}...'")

            # Process immediately (BLOCKING)
            country = extract_country(user_text)
            print(f"[A2A/COUNTRY] Extracted country: '{country}'")

            if not country:
                result_text = "Please specify a country (e.g., 'tell me about Kenya')."
            else:
                try:
                    result_text = await asyncio.wait_for(
                        country_summary_with_fact(country), timeout=25.0
                    )
                except asyncio.TimeoutError:
                    result_text = (
                        f"Sorry, gathering information about {country} took too long."
                    )

            # Create messages
            agent_msg = {
                "kind": "message",
                "role": "agent",
                "parts": [{"kind": "text", "text": result_text}],
                "messageId": str(uuid4()),
                "taskId": task_id,
            }

            user_msg = {
                "kind": "message",
                "role": "user",
                "parts": msg_data.get("parts", []),
                "messageId": original_message_id,
            }

            # Build COMPLETED response (blocking mode)
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "id": task_id,
                    "contextId": context_id,
                    "status": {
                        "state": "completed",  # Use 'completed' not 'running'
                        "timestamp": datetime.utcnow().isoformat(),
                        "message": agent_msg,
                    },
                    "artifacts": [],
                    "history": [user_msg, agent_msg],
                    "kind": "task",
                },
            }

            print(f"[A2A/COUNTRY] ✅ Returned COMPLETED response for '{country}'")
            return JSONResponse(status_code=200, content=response)

        # Method not found
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                    "data": {"supported_methods": ["message/send"]},
                },
            },
        )

    except ValueError as ve:
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32602,
                    "message": "Invalid params",
                    "data": {"details": str(ve)},
                },
            },
        )
    except Exception as e:
        print(f"[A2A/COUNTRY] ❌ Error: {traceback.format_exc()}")
        return JSONResponse(
            status_code=200,
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
