"""Tests du parser HSBC (XLSX). Le parser est NEUTRE : il rend TOUTES les lignes
de mouvement, y compris les virements internes (EHS GROUP FRANCE / Treso) et les
frais — leur filtrage est métier (service/bank_match), pas du ressort du parser.

La fixture est régénérée si elle est absente (voir make_hsbc_sample.py). Pour
tester sur le vrai relevé HSBC anonymisé, déposer le .xlsx dans fixtures/ et
adapter FIXTURE.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from integration.hsbc_parser import parse_hsbc, parse_hsbc_xlsx

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURES / "hsbc_sample.xlsx"


@pytest.fixture(scope="module")
def sample_bytes() -> bytes:
    if not FIXTURE.exists():
        from fixtures.make_hsbc_sample import build_workbook

        build_workbook().save(FIXTURE)
    return FIXTURE.read_bytes()


def test_parses_all_movement_lines(sample_bytes):
    txs = parse_hsbc_xlsx(sample_bytes)
    # 6 mouvements ; les en-têtes de compte répétés (IBAN/BIC/solde) sont ignorés.
    assert len(txs) == 6
    assert all(tx.source == "hsbc" for tx in txs)


def test_dispatch_by_extension(sample_bytes):
    assert parse_hsbc(sample_bytes, "releve.xlsx") == parse_hsbc_xlsx(sample_bytes)
    with pytest.raises(ValueError):
        parse_hsbc(sample_bytes, "releve.csv")


def test_credit_and_debit_split(sample_bytes):
    txs = parse_hsbc_xlsx(sample_bytes)
    by_ref = {tx.ref: tx for tx in txs}

    credit_tx = by_ref["REF0001"]
    assert credit_tx.credit == Decimal("12500.00")
    assert credit_tx.debit is None

    debit_tx = by_ref["REF0003"]
    assert debit_tx.debit == Decimal("18.50")
    assert debit_tx.credit is None


def test_dates_parsed_ddmmyyyy(sample_bytes):
    txs = parse_hsbc_xlsx(sample_bytes)
    by_ref = {tx.ref: tx for tx in txs}
    tx = by_ref["REF0005"]
    assert tx.op_date == date(2026, 1, 9)
    assert tx.value_date == date(2026, 1, 10)


def test_encoding_normalized(sample_bytes):
    txs = parse_hsbc_xlsx(sample_bytes)
    labels = {tx.ref: tx.label for tx in txs}
    # Les '?' parasites sont remplacés par des espaces puis compactés.
    assert "?" not in labels["REF0001"]
    assert labels["REF0001"] == "VIREMENT Tesla FR FACTURE 260001"
    assert labels["REF0004"] == "PRLV Fournisseur XYZ"


def test_internal_transfers_and_fees_are_present(sample_bytes):
    """Critère clé : le parser NE filtre PAS les internes (EHS GROUP FRANCE/Treso)
    ni les frais. Ils doivent figurer dans le retour."""
    txs = parse_hsbc_xlsx(sample_bytes)
    labels = [tx.label for tx in txs]

    internal = [l for l in labels if "EHS GROUP FRANCE" in l]
    assert len(internal) == 2, "les virements internes doivent être présents"
    assert any("Treso" in l for l in internal)

    assert any("FRAIS" in l for l in labels), "les frais doivent être présents"


def test_thousands_separator_parsed(sample_bytes):
    txs = parse_hsbc_xlsx(sample_bytes)
    by_ref = {tx.ref: tx for tx in txs}
    assert by_ref["REF0002"].credit == Decimal("50000.00")
    assert by_ref["REF0006"].debit == Decimal("50000.00")
