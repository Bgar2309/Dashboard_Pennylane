"""Tests du ReminderService : orchestration aging + banque + historique.

On câble les VRAIS services (LedgerService, BankMatchService, DraftGenerator,
Storage sur fichier temporaire) et on injecte un faux client Pennylane (sert une
liste fixe de factures + transactions Revolut, aucun réseau). On vérifie :
  - un client couvert par un match HSBC est ``blocked_by_payment=True`` ;
  - ``generate_draft`` n'écrit RIEN dans l'historique ;
  - ``confirm_sent`` crée bien une entrée de relance.
"""
from datetime import date
from decimal import Decimal

import pytest

from core.models import BankTransaction, Invoice, ReminderLevel
from service.bank_match import BankMatchService
from service.ledger import LedgerService
from service.reminders.drafts import DraftGenerator
from service.reminders.service import ReminderService
from storage import Storage

TODAY = date(2026, 6, 1)


class FakePennylane:
    """Faux client : sert des factures ouvertes et des transactions Revolut."""

    def __init__(self, invoices: list[Invoice],
                 revolut_txs: list[BankTransaction] | None = None) -> None:
        self._invoices = invoices
        self._revolut_txs = revolut_txs or []

    def list_open_invoices(self) -> list[Invoice]:
        return list(self._invoices)

    def list_bank_transactions(self, since: date | None = None) -> list[BankTransaction]:
        return list(self._revolut_txs)


def _inv(id_: int, number: str, customer_id: int, customer_name: str,
         amount: str, due: date | None = date(2026, 5, 15)) -> Invoice:
    return Invoice(
        id=id_, number=number, customer_id=customer_id,
        customer_name=customer_name, date=date(2026, 4, 1), due_date=due,
        amount=Decimal(amount), currency="EUR", paid=False,
        remaining_amount=Decimal(amount),
    )


def _hsbc(ref: str, label: str, credit: str) -> BankTransaction:
    return BankTransaction(
        ref=ref, value_date=date(2026, 5, 20), op_date=date(2026, 5, 20),
        label=label, client_ref=None, credit=Decimal(credit), debit=None,
        source="hsbc",
    )


@pytest.fixture
def storage(tmp_path):
    s = Storage(str(tmp_path / "relance.db"))
    s.init_schema()
    yield s
    s.close()


@pytest.fixture
def env(storage):
    """ReminderService câblé sur de vrais services + faux Pennylane.

    - Facture 260001 (Acme, 100€) : sera couverte par un virement HSBC.
    - Facture 260002 (Globex, 200€) : non couverte.
    """
    invoices = [
        _inv(1, "260001", 10, "Acme SARL", "100.00"),
        _inv(2, "260002", 20, "Globex SA", "200.00"),
    ]
    pennylane = FakePennylane(invoices, revolut_txs=[])
    ledger = LedgerService(pennylane, storage)
    bank_match = BankMatchService(storage)
    drafts = DraftGenerator()
    service = ReminderService(ledger, bank_match, storage, drafts)
    return service, storage


def test_hsbc_match_blocks_payment(env):
    """Un client dont une facture est couverte par un virement HSBC (STRONG)
    apparaît avec ``blocked_by_payment=True`` ; les autres restent à False."""
    service, _ = env
    # Virement HSBC qui mentionne le n° 260001 pour le montant exact -> STRONG.
    hsbc_txs = [_hsbc("HSBC-1", "VIR RECU 260001 ACME", "100.00")]

    rows = service.dunning_view(TODAY, hsbc_txs=hsbc_txs)
    by_id = {row.customer.id: row for row in rows}

    assert by_id[10].blocked_by_payment is True
    assert by_id[20].blocked_by_payment is False


def test_generate_draft_writes_nothing(env):
    """generate_draft rend du texte mais NE LOGUE RIEN dans reminders_log."""
    service, storage = env
    before = len(storage.list_reminders())

    text = service.generate_draft(customer_id=10, today=TODAY)

    assert isinstance(text, str) and text.strip()
    assert "260001" in text  # la facture due figure dans le brouillon
    assert len(storage.list_reminders()) == before == 0


def test_confirm_sent_creates_entry(env):
    """confirm_sent est le SEUL point qui écrit l'historique."""
    service, storage = env
    assert storage.get_last_reminder(10) is None

    entry = service.confirm_sent(
        customer_id=10, level=ReminderLevel.FIRST,
        invoice_numbers=["260001"], note="envoyé par mail",
    )

    assert entry.id is not None
    assert entry.customer_id == 10
    assert entry.customer_name == "Acme SARL"  # résolu via les factures ouvertes
    assert entry.level is ReminderLevel.FIRST
    assert entry.invoice_numbers == ["260001"]

    logged = storage.list_reminders(customer_id=10)
    assert len(logged) == 1
    assert logged[0].note == "envoyé par mail"


def test_revolut_match_blocks_payment(storage):
    """Le blocage prend aussi en compte les transactions Revolut (via Pennylane),
    sans qu'aucun virement HSBC ne soit fourni."""
    invoices = [_inv(2, "260002", 20, "Globex SA", "200.00")]
    revolut = [_hsbc("REV-1", "PAYMENT 260002 GLOBEX", "200.00")]
    revolut[0].source = "revolut"
    pennylane = FakePennylane(invoices, revolut_txs=revolut)
    service = ReminderService(LedgerService(pennylane, storage),
                              BankMatchService(storage), storage, DraftGenerator())

    rows = service.dunning_view(TODAY)
    assert {r.customer.id: r.blocked_by_payment for r in rows} == {20: True}


def test_recently_reminded_customer_is_masked(env):
    """Un client relancé il y a moins de ``min_days_between_reminders`` jours et
    dont le niveau n'escalade pas est masqué de la vue (anti-spam)."""
    service, storage = env
    # On loggue une relance FIRST aujourd'hui pour Acme (bucket D0_30 -> FIRST).
    service.confirm_sent(10, ReminderLevel.FIRST, ["260001"])

    rows = service.dunning_view(TODAY, min_days_between_reminders=8)
    ids = {row.customer.id for row in rows}

    assert 10 not in ids   # masqué : relancé aujourd'hui
    assert 20 in ids       # jamais relancé : toujours visible
