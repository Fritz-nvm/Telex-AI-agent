from app.core.llm_client import LLMClient

class CountryService:
    def __init__(self):
        self.llm_client = LLMClient()

    def get_country_facts(self, country_name: str) -> dict:
        facts = self.llm_client.fetch_country_facts(country_name)
        return facts

    def get_cultural_information(self, country_name: str) -> dict:
        cultural_info = self.llm_client.fetch_cultural_information(country_name)
        return cultural_info

    def get_country_info(self, country_name: str) -> dict:
        facts = self.get_country_facts(country_name)
        cultural_info = self.get_cultural_information(country_name)
        return {
            "facts": facts,
            "cultural_information": cultural_info
        }