"""KPIs dashboard : encours total, DSO, retard moyen, top retardataires, répartition aging.
Consomme des CustomerDunningRow déjà construits. Pas de réseau, pas d'écriture.
"""
from decimal import Decimal

from core.models import CustomerDunningRow
from service.ledger import LedgerService
from storage import Storage


class StatsService:
    def __init__(self, ledger: LedgerService, storage: Storage) -> None:
        raise NotImplementedError

    def dashboard_kpis(self, rows: list[CustomerDunningRow]) -> dict:
        raise NotImplementedError

    def aging_distribution(self, rows: list[CustomerDunningRow]) -> dict[str, Decimal]:
        raise NotImplementedError

    def top_overdue(self, rows: list[CustomerDunningRow], n: int = 10) -> list[dict]:
        raise NotImplementedError
