"""Tests du service de rapprochement bancaire (BankMatchService).

Transactions inspirées du relevé réel EHS :
- GALLIN (facture 260604), SIGNAL CONCEPT (facture 260864),
- le virement interne EHS GROUP FRANCE / Treso doit être REJETÉ.
"""
from datetime import date
from decimal import Decimal

import pytest

from core.models import BankTransaction, Invoice, MatchConfidence
from service.bank_match import BankMatchService
from storage import Storage


@pytest.fixture
def service(tmp_path):
    store = Storage(str(tmp_path / "relance.db"))
    store.init_schema()
    yield BankMatchService(store)
    store.close()


def _tx(ref: str, label: str, credit: str | None = None,
        debit: str | None = None) -> BankTransaction:
    return BankTransaction(
        ref=ref, value_date=date(2026, 6, 4), op_date=date(2026, 6, 4),
        label=label, client_ref=None,
        credit=Decimal(credit) if credit is not None else None,
        debit=Decimal(debit) if debit is not None else None,
    )


def _invoice(id_: int, number: str, customer_name: str, amount: str) -> Invoice:
    return Invoice(
        id=id_, number=number, customer_id=id_, customer_name=customer_name,
        date=date(2026, 5, 1), due_date=date(2026, 6, 1),
        amount=Decimal(amount), currency="EUR", paid=False,
        remaining_amount=Decimal(amount),
    )


GALLIN = _invoice(1, "260604", "GALLIN", "2400.00")
SIGNAL = _invoice(2, "260864", "SIGNAL CONCEPT", "1530.50")


# --- is_client_payment ---------------------------------------------------
def test_credit_client_is_payment(service):
    tx = _tx("R1", "VIR SEPA GALLIN FACTURE 260604", credit="2400.00")
    assert service.is_client_payment(tx) is True


def test_debit_is_not_payment(service):
    tx = _tx("R2", "VIR SEPA GALLIN", debit="500.00")
    assert service.is_client_payment(tx) is False


def test_internal_transfer_rejected(service):
    # Le virement interne / trésorerie ne doit JAMAIS être pris pour un paiement client.
    tx = _tx("R3", "VIR INTERNE EHS GROUP FRANCE TRESO", credit="50000.00")
    assert service.is_client_payment(tx) is False


def test_treso_rejected_case_and_space_insensitive(service):
    tx = _tx("R4", "virement   treso   mensuel", credit="10000.00")
    assert service.is_client_payment(tx) is False


def test_bank_fee_rejected(service):
    tx = _tx("R5", "TVA/FACT MENSUELLE", credit="12.00")
    assert service.is_client_payment(tx) is False


def test_zero_credit_not_payment(service):
    tx = _tx("R6", "VIR GALLIN", credit="0.00")
    assert service.is_client_payment(tx) is False


# --- extract_invoice_numbers ---------------------------------------------
def test_extract_plain_number(service):
    assert service.extract_invoice_numbers("VIR GALLIN FAC 260604") == ["260604"]


def test_extract_with_ca_prefix(service):
    assert service.extract_invoice_numbers("REGLT CA 260864") == ["260864"]


def test_extract_none(service):
    assert service.extract_invoice_numbers("VIREMENT DIVERS") == []


# --- match : STRONG ------------------------------------------------------
def test_strong_number_and_amount(service):
    tx = _tx("R10", "VIR SEPA GALLIN FACTURE 260604", credit="2400.00")
    matches = service.match([tx], [GALLIN, SIGNAL])
    assert len(matches) == 1
    m = matches[0]
    assert m.confidence is MatchConfidence.STRONG
    assert m.invoice_id == GALLIN.id
    assert "260604" in m.matched_invoice_numbers
    assert m.reason


def test_strong_amount_within_one_euro(service):
    tx = _tx("R11", "REGLT 260604", credit="2400.99")
    matches = service.match([tx], [GALLIN])
    assert matches[0].confidence is MatchConfidence.STRONG


# --- match : MEDIUM ------------------------------------------------------
def test_medium_fuzzy_name_exact_amount(service):
    # Pas de n° de facture, mais nom client présent + montant exact.
    tx = _tx("R20", "VIR SEPA SIGNAL CONCEPT SARL", credit="1530.50")
    matches = service.match([tx], [GALLIN, SIGNAL])
    m = matches[0]
    assert m.confidence is MatchConfidence.MEDIUM
    assert m.invoice_id == SIGNAL.id


# --- match : WEAK --------------------------------------------------------
def test_weak_amount_only(service):
    # Montant exact mais ni n° ni nom concordant.
    tx = _tx("R30", "VIR SEPA INCONNU XYZ", credit="2400.00")
    matches = service.match([tx], [GALLIN])
    assert matches[0].confidence is MatchConfidence.WEAK


def test_none_when_nothing_matches(service):
    tx = _tx("R31", "VIR SEPA INCONNU XYZ", credit="999.99")
    matches = service.match([tx], [GALLIN])
    assert matches[0].confidence is MatchConfidence.NONE
    assert matches[0].invoice_id is None


# --- match : filtrage des transactions -----------------------------------
def test_internal_transfer_not_matched(service):
    internal = _tx("R40", "VIR INTERNE EHS GROUP FRANCE TRESO", credit="2400.00")
    client = _tx("R41", "VIR GALLIN 260604", credit="2400.00")
    matches = service.match([internal, client], [GALLIN])
    refs = {m.bank_ref for m in matches}
    assert "R40" not in refs
    assert "R41" in refs


# --- covered_invoice_ids -------------------------------------------------
def test_covered_includes_strong_and_medium(service):
    strong = _tx("R50", "VIR GALLIN 260604", credit="2400.00")
    medium = _tx("R51", "VIR SIGNAL CONCEPT", credit="1530.50")
    matches = service.match([strong, medium], [GALLIN, SIGNAL])
    covered = service.covered_invoice_ids(matches)
    assert covered == {GALLIN.id, SIGNAL.id}


def test_covered_excludes_weak(service):
    # Seul un WEAK pointe vers SIGNAL : son id ne doit PAS être couvert.
    weak = _tx("R52", "VIR INCONNU XYZ", credit="1530.50")
    matches = service.match([weak], [SIGNAL])
    assert matches[0].confidence is MatchConfidence.WEAK
    assert service.covered_invoice_ids(matches) == set()
