from fastapi import FastAPI
from app.api.v1.countries import router as countries_router
from app.services.scheduler_service import get_scheduler, load_all_jobs_on_startup

app = FastAPI(title="Country Interesting Fact Agent", version="1.0.0")

app.include_router(countries_router, prefix="/v1", tags=["telex"])


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup():
    sched = get_scheduler()
    load_all_jobs_on_startup()
    sched.start()
    print("[SCHEDULER] started")


@app.on_event("shutdown")
async def on_shutdown():
    try:
        get_scheduler().shutdown(wait=False)
        print("[SCHEDULER] stopped")
    except Exception:
        pass
