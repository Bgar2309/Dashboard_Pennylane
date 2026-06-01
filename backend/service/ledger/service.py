"""Construit le grand livre client à un instant T (aging par facture + agrégation).
Ne génère pas de texte, ne fait pas de matching bancaire.
"""
from datetime import date

from core.models import AgingBucket, CustomerDunningRow, Invoice
from integration.pennylane import PennylaneClient
from storage import Storage


class LedgerService:
    def __init__(self, pennylane: PennylaneClient, storage: Storage) -> None:
        raise NotImplementedError

    def get_open_invoices(self, use_cache: bool = True,
                          max_cache_age_s: int = 1800) -> list[Invoice]:
        raise NotImplementedError

    def aging_for(self, invoice: Invoice, today: date) -> AgingBucket:
        raise NotImplementedError

    def build_dunning_rows(self, today: date) -> list[CustomerDunningRow]:
        """Agrège par client : total_due, worst_bucket, suggested_level (hors banque/historique)."""
        raise NotImplementedError
