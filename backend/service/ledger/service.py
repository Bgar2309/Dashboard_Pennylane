"""Construit le grand livre client à un instant T (aging par facture + agrégation).
Ne génère pas de texte, ne fait pas de matching bancaire.

Le cache des factures ouvertes est délégué à Storage : on appelle Pennylane
uniquement si le cache est absent ou plus vieux que ``max_cache_age_s``.
L'agrégation par client (``build_dunning_rows``) calcule le niveau de relance
suggéré SANS historique ni banque : ``last_reminder=None`` et
``blocked_by_payment=False`` sont des placeholders que le module ``reminders``
affinera (croisement avec l'historique et les matchs de paiement).
"""
from datetime import date
from decimal import Decimal

from core.aging import bucket_for, level_for
from core.models import AgingBucket, Customer, CustomerDunningRow, Invoice
from integration.pennylane import PennylaneClient
from storage import Storage

# Ordre croissant de gravité des buckets : sert à déterminer le « pire » bucket
# d'un client (la facture la plus en retard porte le niveau de relance).
_BUCKET_SEVERITY = [
    AgingBucket.NOT_DUE,
    AgingBucket.D0_30,
    AgingBucket.D30_60,
    AgingBucket.D60_90,
    AgingBucket.D90_PLUS,
]


class LedgerService:
    """Grand livre client : factures ouvertes, aging, agrégation par client."""

    def __init__(self, pennylane: PennylaneClient, storage: Storage) -> None:
        self._pennylane = pennylane
        self._storage = storage

    def get_open_invoices(self, use_cache: bool = True,
                          max_cache_age_s: int = 1800) -> list[Invoice]:
        """Factures non soldées, servies depuis le cache si assez frais.

        Si ``use_cache`` et que le cache existe et a moins de ``max_cache_age_s``
        secondes, on rend le cache. Sinon on interroge Pennylane (lecture seule),
        on rafraîchit le cache et on rend le résultat frais.
        """
        if use_cache:
            age = self._storage.cache_age_seconds()
            if age is not None and age <= max_cache_age_s:
                return self._storage.get_cached_invoices()

        invoices = self._pennylane.list_open_invoices()
        self._storage.cache_invoices(invoices)
        return invoices

    def aging_for(self, invoice: Invoice, today: date) -> AgingBucket:
        """Bucket d'ancienneté d'une facture (basé sur sa date d'échéance)."""
        return bucket_for(invoice.due_date, today)

    def build_dunning_rows(self, today: date) -> list[CustomerDunningRow]:
        """Agrège les factures ouvertes par client.

        Pour chaque client : total dû, plus ancienne échéance, pire bucket et
        niveau de relance suggéré. Le niveau est calculé sans historique ni
        banque ici (``last_reminder=None``, ``blocked_by_payment=False``) : le
        module ``reminders`` affinera ensuite.
        """
        invoices = self.get_open_invoices()

        # Regroupe en préservant l'ordre d'apparition des clients.
        groups: dict[int, list[Invoice]] = {}
        for inv in invoices:
            groups.setdefault(inv.customer_id, []).append(inv)

        rows: list[CustomerDunningRow] = []
        for customer_id, open_invoices in groups.items():
            total_due = sum((inv.remaining_amount for inv in open_invoices),
                            Decimal("0"))

            due_dates = [inv.due_date for inv in open_invoices
                         if inv.due_date is not None]
            oldest_due_date = min(due_dates) if due_dates else None

            worst_bucket = max(
                (self.aging_for(inv, today) for inv in open_invoices),
                key=_BUCKET_SEVERITY.index,
            )

            suggested_level = level_for(worst_bucket, last_reminder=None)

            rows.append(CustomerDunningRow(
                customer=Customer(id=customer_id,
                                  name=open_invoices[0].customer_name),
                open_invoices=open_invoices,
                total_due=total_due,
                oldest_due_date=oldest_due_date,
                worst_bucket=worst_bucket,
                suggested_level=suggested_level,
                last_reminder=None,
                blocked_by_payment=False,
            ))
        return rows
