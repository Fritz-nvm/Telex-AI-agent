from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.countries import router as countries_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(countries_router, prefix="/api/v1/countries", tags=["countries"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the Country Facts API!"}