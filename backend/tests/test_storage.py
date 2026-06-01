"""Tests de la couche de persistance Storage (SQLite en fichier temporaire)."""
import time
from datetime import date, datetime
from decimal import Decimal

import pytest

from core.models import (Invoice, MatchConfidence, PaymentMatch, ReminderLevel)
from storage import Storage


@pytest.fixture
def store(tmp_path):
    """Storage neuf sur une DB en fichier temporaire, schéma initialisé."""
    s = Storage(str(tmp_path / "relance.db"))
    s.init_schema()
    yield s
    s.close()


def _invoice(id_: int, number: str, customer_id: int = 1,
             due: date | None = date(2026, 5, 1)) -> Invoice:
    return Invoice(
        id=id_, number=number, customer_id=customer_id,
        customer_name="ACME", date=date(2026, 4, 1), due_date=due,
        amount=Decimal("1200.50"), currency="EUR", paid=False,
        remaining_amount=Decimal("1200.50"),
    )


def _match(bank_ref: str, amount: str = "1200.50",
           confidence: MatchConfidence = MatchConfidence.STRONG,
           paid_at: date | None = None) -> PaymentMatch:
    return PaymentMatch(
        bank_ref=bank_ref, invoice_id=42, invoice_number="260604",
        customer_name="ACME", amount=Decimal(amount), confidence=confidence,
        matched_invoice_numbers=["260604", "260605"], reason="num + montant",
        date=paid_at,
    )


# --- init_schema ---
def test_init_schema_idempotent(tmp_path):
    s = Storage(str(tmp_path / "db.sqlite"))
    s.init_schema()
    s.init_schema()  # ne doit pas lever
    assert s.list_reminders() == []
    assert s.list_matches() == []
    assert s.get_cached_invoices() == []
    s.close()


def test_default_db_path_from_config(monkeypatch, tmp_path):
    import config
    target = tmp_path / "nested" / "relance.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(target))
    s = Storage()  # db_path None -> config.DATABASE_PATH
    s.init_schema()
    assert s.db_path == str(target)
    assert target.exists()
    s.close()


# --- reminders_log ---
def test_log_reminder_returns_entry(store):
    entry = store.log_reminder(
        customer_id=7, customer_name="Tesla",
        level=ReminderLevel.FIRST, invoice_numbers=["260604", "260605"],
        note="par mail",
    )
    assert entry.id >= 1
    assert entry.customer_id == 7
    assert entry.customer_name == "Tesla"
    assert entry.level is ReminderLevel.FIRST
    assert entry.invoice_numbers == ["260604", "260605"]
    assert entry.note == "par mail"
    assert isinstance(entry.sent_at, datetime)


def test_get_last_reminder(store):
    assert store.get_last_reminder(7) is None
    store.log_reminder(7, "Tesla", ReminderLevel.FIRST, ["260604"])
    store.log_reminder(7, "Tesla", ReminderLevel.SECOND, ["260604", "260605"])
    last = store.get_last_reminder(7)
    assert last is not None
    assert last.level is ReminderLevel.SECOND
    assert last.invoice_numbers == ["260604", "260605"]
    # autre client non impacté
    assert store.get_last_reminder(99) is None


def test_list_reminders_order_and_filter(store):
    store.log_reminder(1, "A", ReminderLevel.FIRST, ["1"])
    store.log_reminder(2, "B", ReminderLevel.FIRST, ["2"])
    store.log_reminder(1, "A", ReminderLevel.SECOND, ["3"])

    all_rows = store.list_reminders()
    assert len(all_rows) == 3
    # plus récent d'abord
    assert all_rows[0].invoice_numbers == ["3"]

    only_1 = store.list_reminders(customer_id=1)
    assert len(only_1) == 2
    assert {r.customer_id for r in only_1} == {1}


def test_list_reminders_limit(store):
    for i in range(5):
        store.log_reminder(1, "A", ReminderLevel.FIRST, [str(i)])
    assert len(store.list_reminders(limit=2)) == 2


def test_log_reminder_note_optional(store):
    entry = store.log_reminder(1, "A", ReminderLevel.FORMAL, ["9"])
    assert entry.note is None
    assert store.get_last_reminder(1).note is None


# --- payment_matches ---
def test_save_and_list_matches(store):
    store.save_matches([_match("HSBC-1"), _match("HSBC-2", amount="50.00",
                                                 confidence=MatchConfidence.WEAK)])
    matches = store.list_matches()
    assert len(matches) == 2
    m = matches[-1]  # ordre desc -> dernier inséré en tête, donc [-1] = HSBC-1
    assert m.bank_ref == "HSBC-1"
    assert m.amount == Decimal("1200.50")
    assert isinstance(m.amount, Decimal)
    assert m.confidence is MatchConfidence.STRONG
    assert m.matched_invoice_numbers == ["260604", "260605"]
    assert m.reason == "num + montant"


def test_save_matches_appends(store):
    store.save_matches([_match("A")])
    store.save_matches([_match("B")])
    assert len(store.list_matches()) == 2


def test_clear_matches(store):
    store.save_matches([_match("A"), _match("B")])
    store.clear_matches()
    assert store.list_matches() == []


def test_clear_matches_before_boundary(store):
    """Purge les matchs payés <= frontière, garde ceux payés après."""
    boundary = date(2026, 4, 30)
    store.save_matches([
        _match("OLD", paid_at=date(2026, 4, 15)),   # avant -> supprimé
        _match("EDGE", paid_at=boundary),            # = frontière -> supprimé
        _match("NEW", paid_at=date(2026, 5, 10)),    # après -> conservé
    ])

    removed = store.clear_matches_before(boundary)
    assert removed == 2

    remaining = {m.bank_ref for m in store.list_matches()}
    assert remaining == {"NEW"}


def test_clear_matches_before_keeps_undated(store):
    """Un match sans paid_at (date inconnue) n'est jamais purgé."""
    store.save_matches([_match("NODATE", paid_at=None)])
    assert store.clear_matches_before(date(2026, 5, 1)) == 0
    assert {m.bank_ref for m in store.list_matches()} == {"NODATE"}


def test_list_matches_since(store):
    store.save_matches([_match("OLD")])
    matches = store.list_matches(since=date(2000, 1, 1))
    assert len(matches) == 1
    # une date future exclut tout
    assert store.list_matches(since=date(2999, 1, 1)) == []


def test_save_matches_empty(store):
    store.save_matches([])
    assert store.list_matches() == []


# --- invoice_cache ---
def test_cache_and_get_invoices(store):
    invs = [_invoice(10, "260010"), _invoice(11, "260011", due=None)]
    store.cache_invoices(invs)
    cached = store.get_cached_invoices()
    assert len(cached) == 2
    assert cached[0].id == 10
    assert cached[0].number == "260010"
    assert cached[0].amount == Decimal("1200.50")
    assert cached[0].due_date == date(2026, 5, 1)
    assert cached[1].due_date is None
    assert cached[0].paid is False


def test_cache_invoices_replaces(store):
    store.cache_invoices([_invoice(1, "a"), _invoice(2, "b")])
    store.cache_invoices([_invoice(3, "c")])
    cached = store.get_cached_invoices()
    assert len(cached) == 1
    assert cached[0].id == 3


def test_cache_age_seconds(store):
    assert store.cache_age_seconds() is None
    store.cache_invoices([_invoice(1, "a")])
    time.sleep(0.05)
    age = store.cache_age_seconds()
    assert age is not None
    assert age >= 0.0


def test_get_cached_invoices_empty(store):
    assert store.get_cached_invoices() == []


# --- persistance réelle (reouverture du fichier) ---
def test_persistence_across_instances(tmp_path):
    path = str(tmp_path / "persist.db")
    s1 = Storage(path)
    s1.init_schema()
    s1.log_reminder(1, "A", ReminderLevel.FIRST, ["260604"], note="hi")
    s1.close()

    s2 = Storage(path)
    s2.init_schema()  # idempotent, ne doit pas effacer
    last = s2.get_last_reminder(1)
    assert last is not None
    assert last.invoice_numbers == ["260604"]
    assert last.note == "hi"
    s2.close()
