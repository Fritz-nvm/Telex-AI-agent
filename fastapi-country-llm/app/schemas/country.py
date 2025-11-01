from pydantic import BaseModel
from typing import List, Optional

class CountryBase(BaseModel):
    name: str
    capital: str
    region: str
    population: int
    area: float

class CountryCreate(CountryBase):
    pass

class CountryResponse(CountryBase):
    facts: Optional[List[str]] = None
    cultural_info: Optional[str] = None

    class Config:
        orm_mode = True