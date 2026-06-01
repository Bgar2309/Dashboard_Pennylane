"""Point d'entrée FastAPI : monte les routers, configure CORS, expose /api/health.

Le schéma SQLite est initialisé au démarrage (lifespan). Toute la logique vit
dans les services ; ce module ne fait que câbler l'application.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from api.deps import get_storage
from api.routers import bank, ledger, reminders, stats


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise le schéma SQLite avant de servir les requêtes."""
    get_storage().init_schema()
    yield


app = FastAPI(title="Relance EHS", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ledger.router)
app.include_router(reminders.router)
app.include_router(bank.router)
app.include_router(stats.router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    """Sonde de vie : renvoie ``{"status": "ok"}``."""
    return {"status": "ok"}
