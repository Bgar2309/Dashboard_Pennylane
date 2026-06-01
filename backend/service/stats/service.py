"""KPIs dashboard : encours total, DSO, retard moyen, top retardataires, répartition aging.

Consomme des CustomerDunningRow déjà construits (par service/ledger). On NE recalcule
PAS l'aging brut facture par facture : on s'appuie sur worst_bucket / oldest_due_date /
total_due déjà agrégés par ligne. Pas de réseau, pas d'écriture.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from core.models import AgingBucket, CustomerDunningRow, ReminderLevel

if TYPE_CHECKING:  # imports lourds (httpx via ledger) réservés au typage
    from service.ledger import LedgerService
    from storage import Storage

_ZERO = Decimal("0")
_DAY = Decimal("0.1")  # précision des KPI exprimés en jours


def _quantize_days(value: Decimal) -> Decimal:
    return value.quantize(_DAY, rounding=ROUND_HALF_UP)


class StatsService:
    """Agrégats de lecture pour le dashboard. Toutes les méthodes sont pures :
    elles ne dépendent que des lignes passées en argument."""

    def __init__(self, ledger: "LedgerService", storage: "Storage") -> None:
        self.ledger = ledger
        self.storage = storage

    # ------------------------------------------------------------------ KPIs
    def dashboard_kpis(self, rows: list[CustomerDunningRow],
                       today: date | None = None) -> dict:
        """KPIs synthétiques du dashboard.

        - encours_total          : somme des total_due de toutes les lignes
        - clients_a_relancer     : nb de clients avec une relance suggérée, hors
                                    paiement en cours (blocked_by_payment)
        - dso_approche           : âge moyen pondéré des créances ouvertes, en jours
                                    (pondéré par remaining_amount des factures ouvertes)
        - retard_moyen_pondere   : retard moyen pondéré par total_due, en jours
                                    (0 pour les lignes non échues)
        - total_par_bucket       : montant total par bucket d'aging
        """
        if today is None:
            today = date.today()

        encours_total = sum((r.total_due for r in rows), _ZERO)

        clients_a_relancer = sum(
            1 for r in rows
            if r.suggested_level is not ReminderLevel.NONE and not r.blocked_by_payment
        )

        return {
            "encours_total": encours_total,
            "clients_a_relancer": clients_a_relancer,
            "dso_approche": self._dso_approche(rows, today),
            "retard_moyen_pondere": self._retard_moyen_pondere(rows, today),
            "total_par_bucket": self.aging_distribution(rows),
        }

    def _dso_approche(self, rows: list[CustomerDunningRow], today: date) -> Decimal:
        """DSO approché : âge moyen des créances ouvertes pondéré par le montant
        restant dû de chaque facture (jours écoulés depuis la date de facture)."""
        total_weight = _ZERO
        weighted_days = _ZERO
        for row in rows:
            for inv in row.open_invoices:
                weight = inv.remaining_amount
                if weight <= _ZERO:
                    continue
                days = Decimal((today - inv.date).days)
                total_weight += weight
                weighted_days += weight * days
        if total_weight == _ZERO:
            return _ZERO
        return _quantize_days(weighted_days / total_weight)

    def _retard_moyen_pondere(self, rows: list[CustomerDunningRow],
                              today: date) -> Decimal:
        """Retard moyen pondéré par total_due. Le retard d'une ligne est le nombre
        de jours depuis oldest_due_date (borné à 0 si non encore échu)."""
        total_weight = _ZERO
        weighted_days = _ZERO
        for row in rows:
            weight = row.total_due
            if weight <= _ZERO or row.oldest_due_date is None:
                continue
            days = max(0, (today - row.oldest_due_date).days)
            total_weight += weight
            weighted_days += weight * Decimal(days)
        if total_weight == _ZERO:
            return _ZERO
        return _quantize_days(weighted_days / total_weight)

    # ------------------------------------------------------------ distribution
    def aging_distribution(self, rows: list[CustomerDunningRow]) -> dict[str, Decimal]:
        """Montant total par bucket d'aging (basé sur worst_bucket de chaque ligne).

        Tous les buckets sont présents (0 si vide) pour un rendu de graphe stable.
        """
        dist: dict[str, Decimal] = {b.value: _ZERO for b in AgingBucket}
        for row in rows:
            dist[row.worst_bucket.value] += row.total_due
        return dist

    # --------------------------------------------------------------- top liste
    def top_overdue(self, rows: list[CustomerDunningRow], n: int = 10) -> list[dict]:
        """Les n clients réellement en retard, triés par total_due décroissant."""
        overdue = [r for r in rows if r.worst_bucket is not AgingBucket.NOT_DUE]
        overdue.sort(key=lambda r: r.total_due, reverse=True)
        return [
            {
                "customer_id": r.customer.id,
                "customer_name": r.customer.name,
                "total_due": r.total_due,
                "worst_bucket": r.worst_bucket.value,
                "oldest_due_date": r.oldest_due_date,
                "suggested_level": r.suggested_level.value,
                "open_invoices_count": len(r.open_invoices),
            }
            for r in overdue[:n]
        ]
