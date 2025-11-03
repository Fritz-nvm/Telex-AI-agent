from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import countries
from app.core.logging_config import setup_logging

# Setup logging
logger = setup_logging()

app = FastAPI(
    title="Atlas Country Agent",
    description="Telex A2A integration for country information",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(countries.router, prefix="/v1", tags=["countries"])


@app.get("/")
async def root():
    return {"status": "ok", "service": "Atlas Country Bot", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "Atlas Country Bot"}


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Atlas Country Agent started")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Atlas Country Agent shutting down")
