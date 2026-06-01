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
from core.models import (AgingBucket, Customer, CustomerDunningRow,
                         CustomerStatement, Invoice, PaymentMatch,
                         StatementEntry)
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

        # Regroupe par customer_id (jamais par nom) en préservant l'ordre
        # d'apparition : aucune facture n'est perdue. Les factures « Client
        # inconnu » portent customer_id == 0 et forment donc leur propre ligne,
        # visible comme les autres.
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

    # ------------------------------------------------------------------ #
    # Relevé de compte client
    # ------------------------------------------------------------------ #
    def build_statement(self, customer_id: int) -> CustomerStatement:
        """Relevé de compte complet d'un client.

        Fusionne TOUTES ses factures (payées ET impayées, archivées comprises)
        et tous les paiements rapprochés le concernant en une suite d'écritures
        triées par date croissante. Une facture est portée au débit (créance),
        un paiement au crédit (règlement). Chaque écriture porte le solde
        courant cumulé ; le relevé porte le solde final.
        """
        invoices = [inv for inv in self._pennylane.list_all_invoices()
                    if inv.customer_id == customer_id]
        matches = self._matches_for_customer(customer_id, invoices)

        entries: list[StatementEntry] = []
        for inv in invoices:
            entries.append(StatementEntry(
                date=inv.date,
                type="facture",
                label=f"Facture {inv.number}",
                number=inv.number,
                debit=inv.amount,
                credit=None,
                balance=Decimal("0"),
            ))
        for m in matches:
            entries.append(StatementEntry(
                date=m.date or date.min,
                type="paiement",
                label=self._payment_label(m),
                number=m.invoice_number,
                debit=None,
                credit=m.amount,
                balance=Decimal("0"),
            ))

        # Tri par date croissante ; à date égale, la facture précède le paiement.
        entries.sort(key=lambda e: (e.date, 0 if e.type == "facture" else 1))

        balance = Decimal("0")
        for e in entries:
            balance += (e.debit or Decimal("0")) - (e.credit or Decimal("0"))
            e.balance = balance

        name = invoices[0].customer_name if invoices else ""
        return CustomerStatement(
            customer=Customer(id=customer_id, name=name),
            entries=entries,
            final_balance=balance,
        )

    def _matches_for_customer(self, customer_id: int,
                              invoices: list[Invoice]) -> list[PaymentMatch]:
        """Paiements rapprochés concernant ce client : un match est retenu si
        sa facture appartient au client (invoice_id) ou si son nom client
        correspond. Les matchs sans rattachement (confidence NONE) sont ignorés.
        """
        invoice_ids = {inv.id for inv in invoices}
        names = {inv.customer_name for inv in invoices if inv.customer_name}
        out: list[PaymentMatch] = []
        for m in self._storage.list_matches():
            if (m.invoice_id is not None and m.invoice_id in invoice_ids) or \
               (m.customer_name and m.customer_name in names):
                out.append(m)
        return out

    @staticmethod
    def _payment_label(m: PaymentMatch) -> str:
        if m.invoice_number:
            return f"Règlement facture {m.invoice_number}"
        return f"Règlement {m.bank_ref}"
