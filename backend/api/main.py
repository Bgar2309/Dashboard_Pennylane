"""Point d'entrée FastAPI : CORS, montage des routers, /api/health.

Aucune logique métier ici. Le schéma SQLite est initialisé au startup via
``deps.init_schema``. Chaque router de ``api.routers`` expose un ``router``
(``APIRouter`` préfixé ``/api/...``).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from api import deps
from api.routers import bank, ledger, reminders, stats

app = FastAPI(title="Relance EHS", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _on_startup() -> None:
    deps.init_schema()


app.include_router(ledger.router)
app.include_router(reminders.router)
app.include_router(bank.router)
app.include_router(stats.router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
