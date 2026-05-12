import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from config.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

settings = get_settings()

app = FastAPI(
    title="Vivienda Scraper API",
    description="Search for properties for sale across Spanish real-estate platforms.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
