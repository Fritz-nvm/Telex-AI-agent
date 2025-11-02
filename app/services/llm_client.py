import httpx
from app.core.config import settings


def _build_prompt(country: str) -> str:
    return f"""
Provide ONE interesting, specific cultural fact about {country}.
Constraints:
- 1 short paragraph (<= 60 words).
- Avoid politics, NSFW, stereotypes, or unverified claims.
- Prefer festivals, food, arts, etiquette, traditions, or language.
- No emojis.
""".strip()


async def cultural_fact(country: str) -> str:
    """
    Generates one concise cultural fact using Groq's OpenAI-compatible Chat API.
    """
    if not country:
        return "Please provide a country name."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.GROQ_MODEL,
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
    except httpx.HTTPError as e:
        print(
            f"[GROQ ERROR] {e.response.status_code if e.response else 'N/A'} {getattr(e.response, 'text', '')}"
        )
        return "Sorry, I couldn't generate a cultural fact right now."
    except Exception as e:
        print(f"[GROQ ERROR] {e}")
        return "Sorry, I couldn't generate a cultural fact right now."
