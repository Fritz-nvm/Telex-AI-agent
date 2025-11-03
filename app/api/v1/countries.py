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


# ...existing code...


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


def _make_agent_message(task_id: str, text: str) -> TelexMessage:
    """Create a valid Telex agent message using Pydantic schema."""
    return TelexMessage(
        kind="message",
        role="agent",
        parts=[MessagePart(kind="text", text=text)],
        messageId=str(uuid4()),
        taskId=task_id,
    )


# ...existing imports...
async def push_to_telex(
    push_config: PushNotificationConfig,
    agent_msg: TelexMessage,
    task_id: str,
    context_id: str,
    original_msg: TelexMessage,
) -> bool:
    """
    Push final result to Telex webhook.
    Match the exact structure from successful crypto agent response.
    """
    headers = {
        "Authorization": f"Bearer {push_config.token}",
        "Content-Type": "application/json",
    }

    # Build user message for history (from original request)
    user_message = {
        "kind": "message",
        "role": "user",
        "parts": [
            {
                "kind": "text",
                "text": original_msg.parts[0].text,
                "data": None,
                "file_url": None,
            }
        ],
        "messageId": original_msg.messageId,
        "taskId": None,
        "metadata": original_msg.metadata if original_msg.metadata else None,
    }

    # Build agent message matching crypto agent structure
    agent_message = {
        "kind": "message",
        "role": "agent",
        "parts": [
            {
                "kind": "text",
                "text": agent_msg.parts[0].text,
                "data": None,
                "file_url": None,
            }
        ],
        "messageId": agent_msg.messageId,
        "taskId": None,  # Set to None like crypto agent
        "metadata": None,
    }

    # Build result matching crypto agent structure
    result_dict = {
        "id": task_id,
        "contextId": context_id,
        "status": {
            "state": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "message": agent_message,
        },
        "artifacts": [],
        "history": [user_message, agent_message],  # Include both messages
        "kind": "task",
    }

    # Create JSON-RPC response
    payload = {"jsonrpc": "2.0", "id": task_id, "result": result_dict, "error": None}

    print(f"[PUSH] Pushing to: {push_config.url}")
    print(f"[PUSH] Task ID: {task_id}")
    print(f"[PUSH] Message preview: {agent_msg.parts[0].text[:100]}...")
    print(
        f"[PUSH] Payload structure: jsonrpc={payload['jsonrpc']}, has_result={bool(payload.get('result'))}, has_error={payload.get('error') is not None}"
    )
    print(f"[PUSH] History length: {len(result_dict['history'])}")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(push_config.url, headers=headers, json=payload)
            response.raise_for_status()
            print(f"[PUSH] ✅ Success! Status: {response.status_code}")
            print(f"[PUSH] Response: {response.text}")
            return True
    except httpx.HTTPStatusError as e:
        print(f"[PUSH] ❌ HTTP Error {e.response.status_code}")
        print(f"[PUSH] Response body: {e.response.text}")
        return False
    except httpx.TimeoutException:
        print(f"[PUSH] ❌ Timeout pushing to Telex webhook")
        return False
    except Exception as e:
        print(f"[PUSH] ❌ Push failed: {traceback.format_exc()}")
        return False


async def process_and_push(
    user_text: str,
    task_id: str,
    context_id: str,
    push_config: PushNotificationConfig,
    original_msg: TelexMessage,
):
    """
    Background task to process request and push result to Telex.
    Must complete within ~25 seconds to avoid timeout.
    Uses validated schemas.
    """
    print(f"[PUSH] Starting background task for task_id={task_id}")
    print(f"[PUSH] Input text: {user_text[:100]}...")

    try:
        # Extract country with better error handling
        country = extract_country(user_text)
        print(f"[PUSH] Extracted country: '{country}'")

        if not country:
            result_text = "Please specify a country name (e.g., 'tell me about Kenya')."
        else:
            # Process with aggressive timeout (leave 5 seconds for push)
            try:
                result_text = await asyncio.wait_for(
                    country_summary_with_fact(country), timeout=20.0
                )
                print(f"[PUSH] Generated response length: {len(result_text)}")
            except asyncio.TimeoutError:
                print(f"[PUSH] ⏱️ Timeout processing {country}")
                result_text = f"Sorry, gathering information about {country} took too long. Please try again."
            except Exception as e:
                print(f"[PUSH] Processing error: {traceback.format_exc()}")
                result_text = f"Sorry, I encountered an error processing {country}."

    except Exception as e:
        print(f"[PUSH] Extraction error: {traceback.format_exc()}")
        result_text = f"Sorry, I encountered an error: {str(e)}"

    # Create validated agent message
    agent_msg = _make_agent_message(task_id, result_text)

    # Push to Telex webhook - FIXED: pass original_msg
    success = await push_to_telex(
        push_config, agent_msg, task_id, context_id, original_msg
    )

    if success:
        print(f"[PUSH] ✅ Completed successfully for task_id={task_id}")
    else:
        print(f"[PUSH] ❌ Failed to deliver result for task_id={task_id}")


# ...rest of the code stays the same...


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


@router.post("/a2a/country_info", response_model=JSONRPCResponse)
async def a2a_country(request: Request):
    """
    JSON-RPC A2A endpoint supporting both blocking and non-blocking modes.
    Uses Pydantic schemas for validation.
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

    # Validate JSON-RPC request using schema
    try:
        rpc_request = JSONRPCRequest(**body)
    except ValidationError as e:
        print(f"[A2A/COUNTRY] Validation error: {e}")
        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {
                    "code": -32600,
                    "message": "Invalid Request",
                    "data": {"details": str(e)},
                },
            },
        )

    req_id = rpc_request.id
    method = rpc_request.method
    params = rpc_request.params

    # Extract and validate configuration
    config_data = params.get("configuration") or {}
    push_cfg_data = config_data.get("pushNotificationConfig")

    try:
        config = Configuration(**config_data)
        push_config = PushNotificationConfig(**push_cfg_data) if push_cfg_data else None
    except ValidationError as e:
        print(f"[A2A/COUNTRY] Config validation error: {e}")
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32602,
                    "message": "Invalid configuration",
                    "data": {"details": str(e)},
                },
            }
        )

    blocking = config.blocking
    print(
        f"[A2A/COUNTRY] blocking={blocking} has_push_config={push_config is not None}"
    )

    try:
        if method == "message/send":
            msg_data = params.get("message")
            if not msg_data:
                raise ValueError("Missing 'message' in params")

            # Validate message using schema
            try:
                msg = TelexMessage(**msg_data)
            except ValidationError as e:
                raise ValueError(f"Invalid message format: {e}")

            # Extract user text from message parts
            user_text = ""
            for part in msg.parts:
                if part.kind == "text" and part.text:
                    user_text = part.text.strip()
                    print(f"[A2A/COUNTRY] Extracted text: {user_text[:100]}...")
                    break

            if not user_text:
                raise ValueError("No text content found in message parts")

            task_id = msg.taskId or str(uuid4())
            context_id = params.get("contextId") or str(uuid4())

            # NON-BLOCKING MODE: Return immediately and process async
            if not blocking:
                if not push_config:
                    raise ValueError(
                        "pushNotificationConfig required for non-blocking mode"
                    )

                print(f"[A2A/COUNTRY] Starting async task for task_id={task_id}")

                # Start background processing (fire and forget)
                asyncio.create_task(
                    process_and_push(user_text, task_id, context_id, push_config, msg)
                )

                # Create and validate response
                task_status = TaskStatus(
                    state="running",
                    timestamp=datetime.utcnow().isoformat(),
                    message=None,
                )

                task_result = TaskResult(
                    id=task_id,
                    contextId=context_id,
                    status=task_status,
                    artifacts=[],
                    history=[],
                    kind="task",
                )

                response = JSONRPCResponse(jsonrpc="2.0", id=req_id, result=task_result)

                return JSONResponse(content=response.model_dump(exclude_none=True))

            # BLOCKING MODE: Process and return result
            print(f"[A2A/COUNTRY] Processing in blocking mode")

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
                    print(f"[A2A/COUNTRY] Timeout for {country}")
                    result_text = "Sorry, that took too long. Please try again."

            # Create validated agent message
            agent_msg = _make_agent_message(task_id, result_text)

            # Create validated task status and result
            task_status = TaskStatus(
                state="completed",
                timestamp=datetime.utcnow().isoformat(),
                message=agent_msg,
            )

            task_result = TaskResult(
                id=task_id,
                contextId=context_id,
                status=task_status,
                artifacts=[],
                history=[msg, agent_msg],
                kind="task",
            )

            response = JSONRPCResponse(jsonrpc="2.0", id=req_id, result=task_result)

            return JSONResponse(content=response.model_dump(exclude_none=True))

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
