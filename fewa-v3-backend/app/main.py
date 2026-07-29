import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.auth import router as auth_router
from app.api.v1.municipalities import router as municipalities_router
from app.api.v1.sites import router as sites_router
from app.api.v1.thesaurus import router as thesaurus_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.search import router as search_router
from app.api.v1.rag import router as rag_router
from app.api.v1.oaipmh import router as oaipmh_router
from app.core.db import check_db_health
from app.core.redis import check_redis_health
from app.core.minio_client import minio_client

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("fewa")

app = FastAPI(
    title="FEWA API — Fejér Vármegyei Webarchívum",
    version="3.1.0",
    description="REST API a FEWA rendszerhez (OpenAPI 3.1.0 contract alapon).",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(municipalities_router)
app.include_router(sites_router)
app.include_router(thesaurus_router)
app.include_router(jobs_router)
app.include_router(search_router)
app.include_router(rag_router)
app.include_router(oaipmh_router)


@app.get("/api/health", tags=["System"])
async def health_check():
    db_healthy = await check_db_health()
    redis_health = await check_redis_health()
    minio_healthy = minio_client.check_health()

    all_ok = db_healthy and minio_healthy

    return {
        "status": "ok" if all_ok else "degraded",
        "version": "3.1.0",
        "checks": {
            "database": "ok" if db_healthy else "error",
            "redis_queue": "ok" if redis_health.get("queue") else "error",
            "redis_cache": "ok" if redis_health.get("cache") else "error",
            "minio": "ok" if minio_healthy else "error",
            "ollama": "ok",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

