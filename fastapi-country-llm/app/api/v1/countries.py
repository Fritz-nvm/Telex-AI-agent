from fastapi import APIRouter, HTTPException
from app.services.country_service import CountryService
from app.schemas.country import CountryResponse

router = APIRouter()
country_service = CountryService()

@router.get("/countries/{country_name}", response_model=CountryResponse)
async def get_country_info(country_name: str):
    country_info = await country_service.get_country_info(country_name)
    if not country_info:
        raise HTTPException(status_code=404, detail="Country not found")
    return country_info