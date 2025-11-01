from pydantic import BaseModel

class Country(BaseModel):
    name: str
    capital: str
    population: int
    area: float
    region: str
    subregion: str
    languages: list[str]
    currencies: list[str]
    facts: dict[str, str]  # Additional facts about the country
    cultural_info: dict[str, str]  # Cultural information about the country