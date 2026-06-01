"""Tests de StatsService : KPIs dashboard à partir de CustomerDunningRow montées à la main.

Aucun réseau, aucune DB réelle : ledger et storage sont des sentinelles (non utilisés
par les méthodes, qui sont pures et ne consomment que les lignes passées en argument).
"""
from datetime import date
from decimal import Decimal

import pytest

from core.models import (AgingBucket, Customer, CustomerDunningRow, Invoice,
                         ReminderLevel)
from service.stats import StatsService

TODAY = date(2026, 6, 1)


def _invoice(inv_id: int, customer_id: int, name: str, inv_date: date,
             due_date: date, remaining: str) -> Invoice:
    amount = Decimal(remaining)
    return Invoice(
        id=inv_id,
        number=f"26{inv_id:04d}",
        customer_id=customer_id,
        customer_name=name,
        date=inv_date,
        due_date=due_date,
        amount=amount,
        currency="EUR",
        paid=False,
        remaining_amount=amount,
    )


def _row(customer_id: int, name: str, total_due: str, oldest_due: date | None,
         bucket: AgingBucket, level: ReminderLevel,
         invoices: list[Invoice] | None = None,
         blocked: bool = False) -> CustomerDunningRow:
    return CustomerDunningRow(
        customer=Customer(id=customer_id, name=name, email=f"{name}@x.fr"),
        open_invoices=invoices or [],
        total_due=Decimal(total_due),
        oldest_due_date=oldest_due,
        worst_bucket=bucket,
        suggested_level=level,
        last_reminder=None,
        blocked_by_payment=blocked,
    )


@pytest.fixture
def svc() -> StatsService:
    # ledger / storage non utilisés par les méthodes pures -> sentinelles
    return StatsService(ledger=object(), storage=object())


@pytest.fixture
def rows() -> list[CustomerDunningRow]:
    return [
        # ACME : 90+, gros encours, à relancer
        _row(1, "ACME", "10000.00", date(2026, 1, 1), AgingBucket.D90_PLUS,
             ReminderLevel.FORMAL,
             invoices=[_invoice(1, 1, "ACME", date(2025, 12, 1),
                                date(2026, 1, 1), "10000.00")]),
        # Bolt : 30-60, à relancer
        _row(2, "Bolt", "2000.00", date(2026, 4, 15), AgingBucket.D30_60,
             ReminderLevel.SECOND,
             invoices=[_invoice(2, 2, "Bolt", date(2026, 3, 15),
                                date(2026, 4, 15), "2000.00")]),
        # Cire : 0-30 mais paiement en cours -> pas à relancer
        _row(3, "Cire", "500.00", date(2026, 5, 20), AgingBucket.D0_30,
             ReminderLevel.FIRST,
             invoices=[_invoice(3, 3, "Cire", date(2026, 4, 20),
                                date(2026, 5, 20), "500.00")],
             blocked=True),
        # Dune : pas échu, rien à faire
        _row(4, "Dune", "3000.00", date(2026, 7, 1), AgingBucket.NOT_DUE,
             ReminderLevel.NONE,
             invoices=[_invoice(4, 4, "Dune", date(2026, 6, 1),
                                date(2026, 7, 1), "3000.00")]),
    ]


def test_constructor_keeps_dependencies():
    ledger, storage = object(), object()
    svc = StatsService(ledger=ledger, storage=storage)
    assert svc.ledger is ledger
    assert svc.storage is storage


def test_encours_total(svc, rows):
    kpis = svc.dashboard_kpis(rows, today=TODAY)
    assert kpis["encours_total"] == Decimal("15500.00")


def test_clients_a_relancer_exclut_bloque_et_non_echu(svc, rows):
    kpis = svc.dashboard_kpis(rows, today=TODAY)
    # ACME + Bolt seulement (Cire bloqué, Dune non échu)
    assert kpis["clients_a_relancer"] == 2


def test_total_par_bucket(svc, rows):
    kpis = svc.dashboard_kpis(rows, today=TODAY)
    assert kpis["total_par_bucket"] == {
        AgingBucket.NOT_DUE.value: Decimal("3000.00"),
        AgingBucket.D0_30.value: Decimal("500.00"),
        AgingBucket.D30_60.value: Decimal("2000.00"),
        AgingBucket.D60_90.value: Decimal("0"),
        AgingBucket.D90_PLUS.value: Decimal("10000.00"),
    }


def test_aging_distribution_tous_buckets_presents(svc):
    dist = svc.aging_distribution([])
    assert set(dist) == {b.value for b in AgingBucket}
    assert all(v == Decimal("0") for v in dist.values())


def test_retard_moyen_pondere(svc, rows):
    kpis = svc.dashboard_kpis(rows, today=TODAY)
    # Retards (jours depuis oldest_due, borné à 0) pondérés par total_due :
    #   ACME : 151 j * 10000
    #   Bolt :  47 j *  2000
    #   Cire :  12 j *   500
    #   Dune :   0 j *  3000 (non échu)
    weighted = (151 * 10000 + 47 * 2000 + 12 * 500 + 0 * 3000)
    total = 10000 + 2000 + 500 + 3000
    expected = (Decimal(weighted) / Decimal(total)).quantize(Decimal("0.1"))
    assert kpis["retard_moyen_pondere"] == expected


def test_dso_approche(svc, rows):
    kpis = svc.dashboard_kpis(rows, today=TODAY)
    # Âge depuis date facture pondéré par remaining_amount :
    #   ACME : 182 j * 10000  (2025-12-01 -> 2026-06-01)
    #   Bolt :  78 j *  2000  (2026-03-15 -> 2026-06-01)
    #   Cire :  42 j *   500  (2026-04-20 -> 2026-06-01)
    #   Dune :   0 j *  3000  (2026-06-01 -> 2026-06-01)
    weighted = (182 * 10000 + 78 * 2000 + 42 * 500 + 0 * 3000)
    total = 10000 + 2000 + 500 + 3000
    expected = (Decimal(weighted) / Decimal(total)).quantize(Decimal("0.1"))
    assert kpis["dso_approche"] == expected


def test_kpis_liste_vide(svc):
    kpis = svc.dashboard_kpis([], today=TODAY)
    assert kpis["encours_total"] == Decimal("0")
    assert kpis["clients_a_relancer"] == 0
    assert kpis["dso_approche"] == Decimal("0")
    assert kpis["retard_moyen_pondere"] == Decimal("0")


def test_top_overdue_tri_et_exclut_non_echu(svc, rows):
    top = svc.top_overdue(rows)
    # Dune (NOT_DUE) exclu ; tri par total_due décroissant
    assert [r["customer_name"] for r in top] == ["ACME", "Bolt", "Cire"]
    assert top[0]["total_due"] == Decimal("10000.00")
    assert top[0]["worst_bucket"] == AgingBucket.D90_PLUS.value
    assert top[0]["suggested_level"] == ReminderLevel.FORMAL.value
    assert top[0]["open_invoices_count"] == 1
    assert top[0]["oldest_due_date"] == date(2026, 1, 1)


def test_top_overdue_respecte_n(svc, rows):
    top = svc.top_overdue(rows, n=2)
    assert len(top) == 2
    assert [r["customer_name"] for r in top] == ["ACME", "Bolt"]


def test_top_overdue_liste_vide(svc):
    assert svc.top_overdue([]) == []
