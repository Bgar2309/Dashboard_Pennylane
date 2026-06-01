"""Injection de dépendances FastAPI : singletons Storage / PennylaneClient /
services, assemblés en respectant le graphe d'architecture.

Graphe (haut -> bas) ::

    Storage ─┬─> PennylaneClient ─> LedgerService ─┬─> StatsService
             │                                      │
             ├─> BankMatchService ─────────────────┤
             │                                      └─> ReminderService
             └─> DraftGenerator ────────────────────┘

Chaque ``get_*`` est mémoïsé (``lru_cache``) : une seule instance par process,
partagée entre requêtes. ``init_schema`` est appelé une fois au boot (main).
"""
from functools import lru_cache

import config
from integration.pennylane.client import PennylaneClient
from service.bank_match.service import BankMatchService
from service.ledger.service import LedgerService
from service.reminders.drafts import DraftGenerator
from service.reminders.service import ReminderService
from service.stats.service import StatsService
from storage.db import Storage


@lru_cache
def get_storage() -> Storage:
    """Singleton de persistance (SQLite, chemin ``config.DATABASE_PATH``)."""
    return Storage(config.DATABASE_PATH)


@lru_cache
def get_pennylane_client() -> PennylaneClient:
    """Wrapper REST Pennylane (lecture seule)."""
    return PennylaneClient(config.PENNYLANE_TOKEN, config.PENNYLANE_BASE_URL)


@lru_cache
def get_ledger_service() -> LedgerService:
    return LedgerService(get_pennylane_client(), get_storage())


@lru_cache
def get_bank_match_service() -> BankMatchService:
    return BankMatchService(get_storage())


@lru_cache
def get_draft_generator() -> DraftGenerator:
    return DraftGenerator()


@lru_cache
def get_stats_service() -> StatsService:
    return StatsService(get_ledger_service(), get_storage())


@lru_cache
def get_reminder_service() -> ReminderService:
    return ReminderService(
        get_ledger_service(),
        get_bank_match_service(),
        get_storage(),
        get_draft_generator(),
    )


def init_schema() -> None:
    """Crée le schéma SQLite au démarrage. Idempotent (appelé par main)."""
    get_storage().init_schema()
