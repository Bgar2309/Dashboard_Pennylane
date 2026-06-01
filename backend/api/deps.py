"""Injection de dépendances FastAPI.

Construit le graphe une seule fois (singletons mémorisés) et l'expose via des
fonctions ``get_*`` utilisables avec ``Depends``. Les tests remplacent ces
fonctions via ``app.dependency_overrides`` (services mockés) — d'où le découpage
fin (un getter par brique).

Graphe : Storage -> PennylaneClient
                  -> LedgerService, BankMatchService, StatsService
                  -> ReminderService (orchestrateur).
"""
from __future__ import annotations

from functools import lru_cache

from integration.pennylane import PennylaneClient
from service.bank_match import BankMatchService
from service.ledger import LedgerService
from service.reminders.drafts import DraftGenerator
from service.reminders.service import ReminderService
from service.stats import StatsService
from storage import Storage


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    """Singleton Storage. ``init_schema`` est idempotent : sûr à appeler ici."""
    storage = Storage()
    storage.init_schema()
    return storage


@lru_cache(maxsize=1)
def get_pennylane_client() -> PennylaneClient:
    """Singleton client Pennylane (lecture seule, token depuis config)."""
    return PennylaneClient()


@lru_cache(maxsize=1)
def get_ledger_service() -> LedgerService:
    return LedgerService(get_pennylane_client(), get_storage())


@lru_cache(maxsize=1)
def get_bank_match_service() -> BankMatchService:
    return BankMatchService(get_storage())


@lru_cache(maxsize=1)
def get_stats_service() -> StatsService:
    return StatsService(get_ledger_service(), get_storage())


@lru_cache(maxsize=1)
def get_reminder_service() -> ReminderService:
    return ReminderService(
        ledger=get_ledger_service(),
        bank_match=get_bank_match_service(),
        storage=get_storage(),
        drafts=DraftGenerator(),
    )
