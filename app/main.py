from fastapi import FastAPI
from app.api.v1.countries import router as countries_router

app = FastAPI(title="Country Facts Agent (A2A, Groq)", version="1.0.0")
app.include_router(countries_router, prefix="/v1", tags=["a2a"])


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok"}
