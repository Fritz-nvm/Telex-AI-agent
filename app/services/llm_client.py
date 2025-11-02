import google.generativeai as genai
from app.core.config import settings

# Configure Google GenAI
genai.configure(api_key=settings.GOOGLE_API_KEY)
_model = genai.GenerativeModel(settings.GEMINI_MODEL_ID)


async def cultural_fact(country: str) -> str:
    """
    Get ONE short, safe cultural fact about the given country.
    """
    prompt = f"""
    You are a concise cultural assistant. Provide ONE interesting, specific cultural fact about {country}.
    Constraints:
    - 1 short paragraph (<= 60 words).
    - Avoid politics, NSFW, stereotypes, or unverified claims.
    - Prefer festivals, food, arts, etiquette, traditions, or language.
    - If ambiguity, assume the most likely sovereign state.
    - No emojis.
    """
    try:
        resp = await _model.generate_content_async(prompt.strip())
        text = getattr(resp, "text", None)
        if text:
            return text.strip()
        # Fallback to constructing text from candidates if needed
        if getattr(resp, "candidates", None):
            parts = []
            for c in resp.candidates:
                content = getattr(c, "content", None)
                if content and getattr(content, "parts", None):
                    for p in content.parts:
                        val = getattr(p, "text", "")
                        if val:
                            parts.append(val)
            return (" ".join(parts)).strip() or "No fact available right now."
        return "No fact available right now."
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return "Sorry, I couldn't generate a cultural fact right now."
