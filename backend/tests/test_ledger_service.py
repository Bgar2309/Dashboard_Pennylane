"""Tests du LedgerService : cache des factures ouvertes, aging par facture,
agrégation par client.

On injecte un faux PennylaneClient (compte ses appels, sert une liste fixe) et
un vrai Storage sur fichier temporaire. Aucun réseau, aucune logique métier
dupliquée : on vérifie le câblage cache + l'agrégation.
"""
from datetime import date
from decimal import Decimal

import pytest

from core.models import AgingBucket, Invoice, ReminderLevel
from service.ledger import LedgerService
from storage import Storage

TODAY = date(2026, 6, 1)


class FakePennylane:
    """Faux client : rend une liste fixe et compte les appels réseau."""

    def __init__(self, invoices: list[Invoice]) -> None:
        self._invoices = invoices
        self.calls = 0

    def list_open_invoices(self) -> list[Invoice]:
        self.calls += 1
        return list(self._invoices)


def _inv(id_: int, customer_id: int, customer_name: str,
         due: date | None, remaining: str) -> Invoice:
    return Invoice(
        id=id_, number=str(id_), customer_id=customer_id,
        customer_name=customer_name, date=date(2026, 1, 1), due_date=due,
        amount=Decimal(remaining), currency="EUR", paid=False,
        remaining_amount=Decimal(remaining),
    )


@pytest.fixture
def storage(tmp_path):
    s = Storage(str(tmp_path / "relance.db"))
    s.init_schema()
    yield s
    s.close()


# Jeu de factures : 2 clients, échéances couvrant plusieurs buckets.
INVOICES = [
    _inv(1, 100, "ACME", date(2026, 5, 20), "100.00"),   # 12 j -> 0-30
    _inv(2, 100, "ACME", date(2026, 2, 1), "250.00"),    # ~120 j -> 90+
    _inv(3, 200, "Brady", None, "75.00"),                # pas d'échéance -> NOT_DUE
    _inv(4, 200, "Brady", date(2026, 7, 1), "30.00"),    # future -> NOT_DUE
]


# --- get_open_invoices : câblage du cache ---
def test_get_open_invoices_fetches_then_caches(storage):
    pny = FakePennylane(INVOICES)
    svc = LedgerService(pny, storage)

    first = svc.get_open_invoices()
    assert pny.calls == 1
    assert [i.id for i in first] == [1, 2, 3, 4]
    # Le cache a bien été rempli.
    assert [i.id for i in storage.get_cached_invoices()] == [1, 2, 3, 4]


def test_get_open_invoices_uses_fresh_cache(storage):
    pny = FakePennylane(INVOICES)
    svc = LedgerService(pny, storage)

    svc.get_open_invoices()              # remplit le cache (1 appel)
    again = svc.get_open_invoices()      # cache frais -> pas de nouvel appel
    assert pny.calls == 1
    assert [i.id for i in again] == [1, 2, 3, 4]


def test_get_open_invoices_refetches_when_cache_stale(storage):
    pny = FakePennylane(INVOICES)
    svc = LedgerService(pny, storage)

    svc.get_open_invoices()
    # max_cache_age_s=0 force le cache à être considéré comme périmé.
    svc.get_open_invoices(max_cache_age_s=0)
    assert pny.calls == 2


def test_get_open_invoices_bypasses_cache_when_disabled(storage):
    pny = FakePennylane(INVOICES)
    svc = LedgerService(pny, storage)

    svc.get_open_invoices()
    svc.get_open_invoices(use_cache=False)
    assert pny.calls == 2


# --- aging_for : délègue à core.bucket_for ---
@pytest.mark.parametrize("due, expected", [
    (None, AgingBucket.NOT_DUE),
    (date(2026, 7, 1), AgingBucket.NOT_DUE),
    (date(2026, 5, 20), AgingBucket.D0_30),
    (date(2026, 4, 15), AgingBucket.D30_60),
    (date(2026, 3, 15), AgingBucket.D60_90),
    (date(2026, 2, 1), AgingBucket.D90_PLUS),
])
def test_aging_for(storage, due, expected):
    svc = LedgerService(FakePennylane([]), storage)
    assert svc.aging_for(_inv(9, 1, "X", due, "1"), TODAY) == expected


# --- build_dunning_rows : agrégation par client ---
def test_build_dunning_rows_aggregates_per_customer(storage):
    svc = LedgerService(FakePennylane(INVOICES), storage)
    rows = {r.customer.id: r for r in svc.build_dunning_rows(TODAY)}

    assert set(rows) == {100, 200}

    acme = rows[100]
    assert acme.customer.name == "ACME"
    assert acme.total_due == Decimal("350.00")
    assert acme.oldest_due_date == date(2026, 2, 1)
    assert acme.worst_bucket == AgingBucket.D90_PLUS  # la facture la plus en retard
    assert acme.suggested_level == ReminderLevel.FORMAL
    assert [i.id for i in acme.open_invoices] == [1, 2]

    brady = rows[200]
    assert brady.total_due == Decimal("105.00")
    # Seule l'échéance datée compte ; la facture sans échéance est ignorée.
    assert brady.oldest_due_date == date(2026, 7, 1)
    assert brady.worst_bucket == AgingBucket.NOT_DUE  # aucune facture en retard
    assert brady.suggested_level == ReminderLevel.NONE


def test_build_dunning_rows_oldest_due_date_none_when_all_undated(storage):
    invoices = [
        _inv(10, 300, "NoDate", None, "10.00"),
        _inv(11, 300, "NoDate", None, "20.00"),
    ]
    svc = LedgerService(FakePennylane(invoices), storage)
    (row,) = svc.build_dunning_rows(TODAY)
    assert row.oldest_due_date is None


def test_build_dunning_rows_no_history_or_bank(storage):
    svc = LedgerService(FakePennylane(INVOICES), storage)
    for row in svc.build_dunning_rows(TODAY):
        assert row.last_reminder is None
        assert row.blocked_by_payment is False


def test_build_dunning_rows_empty(storage):
    svc = LedgerService(FakePennylane([]), storage)
    assert svc.build_dunning_rows(TODAY) == []
