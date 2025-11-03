import httpx
import json
import re
import traceback
from typing import Optional, Dict, Any
from app.core.config import GROQ_API_KEY, GROQ_MODEL

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def extract_first_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Extract first valid JSON object from text, handling markdown fences."""
    if not text:
        return None

    # Strip markdown code fences
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    candidate = m.group(1) if m else text

    # Find first opening brace
    start = candidate.find("{")
    if start == -1:
        return None

    # Parse with brace counting
    depth = 0
    in_string = False
    escape = False
    quote_char = ""

    for i in range(start, len(candidate)):
        ch = candidate[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote_char:
                in_string = False
        else:
            if ch in ('"', "'"):
                in_string = True
                quote_char = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    chunk = candidate[start : i + 1]
                    try:
                        return json.loads(chunk)
                    except Exception:
                        # Try removing trailing commas
                        chunk = re.sub(r",(\s*[}\]])", r"\1", chunk)
                        try:
                            return json.loads(chunk)
                        except Exception:
                            pass
    return None


async def country_details(country: str) -> Optional[Dict[str, Any]]:
    """Fetch structured country information from Groq."""
    if not country or not GROQ_API_KEY:
        print("[GROQ] Missing country or API key")
        return None

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    schema_note = """
Respond with JSON only (no markdown, no commentary). Structure:
{
  "name": "string",
  "capital": ["string"],
  "region": "string",
  "subregion": "string|null",
  "population_estimate": "integer|null",
  "languages": ["string"],
  "currencies": ["string"],
  "timezones": ["string"],
  "cca2": "string|null",
  "cca3": "string|null"
}
""".strip()

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a geodata assistant. Output JSON only.",
            },
            {
                "role": "user",
                "content": f"Provide structured country info for: {country}\n\n{schema_note}",
            },
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(GROQ_API_URL, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            text = data["choices"][0]["message"]["content"].strip()

            obj = extract_first_json_object(text)
            if obj is None:
                print(f"[GROQ] Could not parse JSON for {country}")

            return obj

    except httpx.HTTPStatusError as e:
        print(f"[GROQ] HTTP {e.response.status_code}: {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"[GROQ] Error: {traceback.format_exc()}")
        return None


async def cultural_fact(country: str) -> str:
    """Generate concise cultural fact about the country."""
    if not country or not GROQ_API_KEY:
        return "Cultural fact unavailable."

    prompt = f"""
Provide ONE interesting, specific cultural fact about {country}.

Constraints:
- 1 short paragraph (<= 60 words)
- Avoid politics, NSFW content, stereotypes
- Prefer: festivals, food, arts, etiquette, traditions, language
- No emojis

Example: "In Japan, the 'Cherry Blossom Viewing' tradition dates back centuries..."
""".strip()

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are a concise cultural assistant."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.6,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(GROQ_API_URL, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"[GROQ] Fact error: {traceback.format_exc()}")
        return "Sorry, I couldn't generate a cultural fact right now."
