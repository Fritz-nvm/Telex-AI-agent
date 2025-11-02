from typing import Optional
import httpx
from app.services.llm_client import cultural_fact

RESTCOUNTRIES_URL = "https://restcountries.com/v3.1/name/{q}?fields=name,capital,region,subregion,population,languages,currencies,timezones,cca2,cca3"


async def fetch_country_details(name: str) -> Optional[dict]:
    url = RESTCOUNTRIES_URL.format(q=name)
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list) and data:
                return data[0]
            return None
        except httpx.HTTPError as e:
            print(f"[RESTCOUNTRIES ERROR] {e}")
            return None


def format_details_and_fact(details: Optional[dict], fact: str) -> str:
    if not details:
        return fact

    name = (
        details.get("name", {}).get("common")
        or details.get("name", {}).get("official")
        or "Unknown country"
    )
    capital = ", ".join(details.get("capital", []) or []) or "N/A"
    region = details.get("region") or "N/A"
    subregion = details.get("subregion") or "N/A"
    population = details.get("population")
    population_s = f"{population:,}" if isinstance(population, int) else "N/A"
    languages = details.get("languages") or {}
    languages_s = ", ".join(sorted(languages.values())) if languages else "N/A"
    currencies = details.get("currencies") or {}
    currency_names = []
    for c in currencies.values():
        nm = c.get("name")
        sym = c.get("symbol")
        currency_names.append(f"{nm} ({sym})" if sym else nm)
    currencies_s = ", ".join([c for c in currency_names if c]) or "N/A"
    timezones = ", ".join(details.get("timezones", []) or []) or "N/A"
    cca2 = details.get("cca2") or ""
    cca3 = details.get("cca3") or ""

    return (
        f"{name} [{cca2 or cca3}]\n"
        f"- Capital: {capital}\n"
        f"- Region: {region} ({subregion})\n"
        f"- Population: {population_s}\n"
        f"- Languages: {languages_s}\n"
        f"- Currencies: {currencies_s}\n"
        f"- Timezones: {timezones}\n"
        f"\nCulture fact: {fact}"
    )


async def country_summary_with_fact(country: str) -> str:
    details = await fetch_country_details(country)
    fact = await cultural_fact(country)
    return format_details_and_fact(details, fact)
