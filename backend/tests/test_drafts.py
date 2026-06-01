"""Tests du générateur de brouillons de relance (templates FR déterministes)."""
from datetime import date
from decimal import Decimal

import pytest

from core.models import Customer, Invoice, ReminderLevel
from service.reminders.drafts import DraftGenerator


def _customer() -> Customer:
    return Customer(id=1, name="ACME SARL", email="compta@acme.fr")


def _invoices() -> list[Invoice]:
    return [
        Invoice(
            id=10,
            number="260001",
            customer_id=1,
            customer_name="ACME SARL",
            date=date(2026, 1, 15),
            due_date=date(2026, 2, 14),
            amount=Decimal("1200.00"),
            currency="EUR",
            paid=False,
            remaining_amount=Decimal("1200.00"),
        ),
        Invoice(
            id=11,
            number="260002",
            customer_id=1,
            customer_name="ACME SARL",
            date=date(2026, 2, 1),
            due_date=date(2026, 3, 3),
            amount=Decimal("350.50"),
            currency="EUR",
            paid=False,
            remaining_amount=Decimal("350.50"),
        ),
    ]


@pytest.mark.parametrize(
    "level", [ReminderLevel.FIRST, ReminderLevel.SECOND, ReminderLevel.FORMAL]
)
def test_render_each_level(level: ReminderLevel) -> None:
    gen = DraftGenerator()
    invoices = _invoices()
    text = gen.render(_customer(), invoices, level, today=date(2026, 6, 1))

    # Texte non vide.
    assert text and text.strip()

    # Les numéros de facture apparaissent.
    for inv in invoices:
        assert inv.number in text

    # Le total dû (1200.00 + 350.50 = 1550.50) apparaît, formaté FR.
    assert "1 550,50" in text
    assert "Total" in text


def test_render_mentions_customer_name() -> None:
    gen = DraftGenerator()
    text = gen.render(_customer(), _invoices(), ReminderLevel.FIRST,
                      today=date(2026, 6, 1))
    assert "ACME SARL" in text


def test_render_tone_differs_per_level() -> None:
    gen = DraftGenerator()
    cust, inv, today = _customer(), _invoices(), date(2026, 6, 1)
    first = gen.render(cust, inv, ReminderLevel.FIRST, today)
    second = gen.render(cust, inv, ReminderLevel.SECOND, today)
    formal = gen.render(cust, inv, ReminderLevel.FORMAL, today)

    assert first != second != formal
    assert "mise en demeure" in formal.lower()


def test_render_rejects_none_level() -> None:
    gen = DraftGenerator()
    with pytest.raises(ValueError):
        gen.render(_customer(), _invoices(), ReminderLevel.NONE,
                   today=date(2026, 6, 1))
