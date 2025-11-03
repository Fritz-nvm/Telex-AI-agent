import httpx
import json
import re
from app.core.config import GROQ_API_KEY, GROQ_MODEL


def _build_prompt(country: str) -> str:
    # ...existing code...
    return f"""
Provide ONE interesting, specific cultural fact about {country}.
Constraints:
- 1 short paragraph (<= 60 words).
- Avoid politics, NSFW, stereotypes, or unverified claims.
- Prefer festivals, food, arts, etiquette, traditions, or language.
- No emojis.
""".strip()


async def country_details(country: str) -> dict | None:
    """
    Ask Groq to return structured country info as JSON.
    Returns a dict or None on error.
    """
    if not country or not GROQ_API_KEY:
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    schema_note = """
Return ONLY valid JSON (no markdown). Use this exact structure:
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
If unknown, use null or [] as appropriate.
If input is ambiguous, choose the most likely sovereign state.
"""
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a careful geodata assistant. Be precise and avoid hallucinations.",
            },
            {
                "role": "user",
                "content": f"Provide structured country info for: {country}\n{schema_note}".strip(),
            },
        ],
        "temperature": 0.2,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"].strip()

            # Strip fenced code if present
            m = re.search(
                r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE
            )
            raw = m.group(1) if m else text

            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
    except Exception as e:
        print(f"[GROQ COUNTRY DETAILS ERROR] {e}")
        return None


async def cultural_fact(country: str) -> str:
    # ...existing code...
    if not country:
        return "Please provide a country name."
    if not GROQ_API_KEY:
        return "LLM not available: missing GROQ_API_KEY."
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You are a concise cultural assistant."},
            {"role": "user", "content": _build_prompt(country)},
        ],
        "temperature": 0.7,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as e:
        code = e.response.status_code if e.response else "N/A"
        body = e.response.text if e.response else ""
        print(f"[GROQ ERROR] {code} {body}")
        if code == 401:
            return "LLM not available: invalid GROQ_API_KEY."
        return "Sorry, I couldn't generate a cultural fact right now."
    except Exception as e:
        print(f"[GROQ ERROR] {e}")
        return "Sorry, I couldn't generate a cultural fact right now."
