from typing import Any, Dict
import requests

class LLMClient:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    def get_country_info(self, country_name: str) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": f"Provide facts and cultural information about {country_name}."
        }
        response = requests.post(self.api_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    def get_multiple_country_info(self, country_names: list) -> Dict[str, Any]:
        results = {}
        for country in country_names:
            results[country] = self.get_country_info(country)
        return results