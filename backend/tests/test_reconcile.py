"""Tests du lettrage maison FIFO + anti-doublon A-Nouveau (core.reconcile)."""
from datetime import date
from decimal import Decimal

from core.reconcile import OpenItem, RawLine, reconcile_account


def _line(
    line_id: int,
    d: str,
    *,
    debit: str = "0",
    credit: str = "0",
    label: str = "",
    opening: bool = False,
    invoice_number: str | None = None,
) -> RawLine:
    """Fabrique une RawLine de façon concise (montants en str -> Decimal)."""
    return RawLine(
        id=line_id,
        date=date.fromisoformat(d),
        debit=Decimal(debit),
        credit=Decimal(credit),
        label=label,
        is_opening_balance=opening,
        invoice_number=invoice_number,
    )


def test_411les_un_seul_open_item():
    """Compte 411LES réel : la seule créance résiduelle est la facture du
    16/04/2026 de 3118,45 €. Les trois A-Nouveau du 01/01/2026 doublonnent des
    factures de fin 2025 déjà présentes et la paire d'annulation du 05/11/2025
    est neutralisée."""
    lines = [
        _line(1, "2025-01-01", debit="1522.00", label="A-Nouveau", opening=True),
        _line(2, "2025-01-08", credit="1522.00", label="Paiement"),
        _line(3, "2025-02-28", debit="3969.56", label="Facture"),
        _line(4, "2025-03-20", debit="2370.80", label="Facture"),
        _line(5, "2025-04-07", credit="3969.56", label="Paiement"),
        _line(6, "2025-04-17", debit="3189.80", label="Facture"),
        _line(7, "2025-04-30", debit="504.00", label="Facture"),
        _line(8, "2025-05-07", credit="2370.80", label="Paiement"),
        _line(9, "2025-06-11", credit="3189.80", label="Paiement"),
        _line(10, "2025-06-18", credit="504.00", label="Paiement"),
        _line(11, "2025-06-26", debit="2599.84", label="Facture"),
        _line(12, "2025-06-26", debit="1127.00", label="Facture"),
        _line(13, "2025-07-30", debit="299.72", label="Facture"),
        _line(14, "2025-08-14", credit="3726.84", label="Paiement"),
        _line(15, "2025-08-25", debit="5157.80", label="Facture"),
        _line(16, "2025-08-26", debit="81.18", label="Facture"),
        _line(17, "2025-09-03", credit="299.72", label="Paiement"),
        _line(18, "2025-09-17", debit="455.56", label="Facture"),
        _line(19, "2025-10-03", credit="5238.98", label="Paiement"),
        _line(20, "2025-11-05", debit="6607.40", label="Facture"),
        _line(21, "2025-11-05", credit="6607.40", label="Annulation"),
        _line(22, "2025-11-05", debit="6607.40", label="Facture (refaite)"),
        _line(23, "2025-11-11", credit="455.56", label="Paiement"),
        _line(24, "2025-11-21", debit="3363.20", label="Facture"),
        _line(25, "2025-12-05", debit="1515.00", label="Facture"),
        _line(26, "2026-01-01", debit="6607.40", label="A-Nouveau", opening=True),
        _line(27, "2026-01-01", debit="3363.20", label="A-Nouveau", opening=True),
        _line(28, "2026-01-01", debit="1515.00", label="A-Nouveau", opening=True),
        _line(29, "2026-01-09", credit="6607.40", label="Paiement"),
        _line(30, "2026-01-26", credit="3363.20", label="Paiement"),
        _line(31, "2026-02-11", credit="1515.00", label="Paiement"),
        _line(32, "2026-04-16", debit="3118.45", label="Facture"),
    ]

    result = reconcile_account(lines, window_start=date(2025, 1, 1))

    assert len(result) == 1
    item = result[0]
    assert item.date == date(2026, 4, 16)
    assert item.amount_remaining == Decimal("3118.45")
    assert item.amount_original == Decimal("3118.45")
    assert item.source_line_id == 32


def test_annulation_neutralisee():
    """Facture + contre-passation même date/montant : la paire disparaît, seule
    la facture refaite (impayée) reste."""
    lines = [
        _line(1, "2025-11-05", debit="6607.40", label="Facture"),
        _line(2, "2025-11-05", credit="6607.40", label="Annulation"),
        _line(3, "2025-11-05", debit="6607.40", label="Facture (refaite)"),
    ]

    result = reconcile_account(lines, window_start=date(2025, 1, 1))

    assert len(result) == 1
    assert result[0].amount_remaining == Decimal("6607.40")


def test_a_nouveau_legitime_conserve():
    """Un A-Nouveau sans facture correspondante avant sa date est un solde
    réellement antérieur (facture d'origine hors fenêtre) : il est conservé
    comme créance, à l'inverse d'un A-Nouveau doublon."""
    lines = [
        _line(1, "2025-01-01", debit="1200.00", label="A-Nouveau", opening=True),
        _line(2, "2025-03-10", debit="500.00", label="Facture"),
    ]

    result = reconcile_account(lines, window_start=date(2025, 1, 1))

    # Aucun crédit : l'A-Nouveau légitime survit comme créance « Solde antérieur ».
    by_id = {item.source_line_id: item for item in result}
    assert 1 in by_id
    assert by_id[1].amount_remaining == Decimal("1200.00")
    assert by_id[1].label == "A-Nouveau"
    assert len(result) == 2


def test_a_nouveau_doublon_exclu():
    """Un A-Nouveau qui reprend une facture déjà présente dans la fenêtre est
    exclu : aucune créance résiduelle après paiement de la facture."""
    lines = [
        _line(1, "2025-12-05", debit="1515.00", label="Facture"),
        _line(2, "2026-01-01", debit="1515.00", label="A-Nouveau", opening=True),
        _line(3, "2026-01-10", credit="1515.00", label="Paiement"),
    ]

    result = reconcile_account(lines, window_start=date(2025, 1, 1))

    assert result == []


def test_paiement_partiel():
    """Paiement partiel : le reliquat de la facture la plus ancienne est exact
    (imputation FIFO du plus ancien au plus récent)."""
    lines = [
        _line(1, "2025-02-01", debit="1000.00", label="Facture A"),
        _line(2, "2025-03-01", debit="400.00", label="Facture B"),
        _line(3, "2025-03-15", credit="600.00", label="Paiement"),
    ]

    result = reconcile_account(lines, window_start=date(2025, 1, 1))

    # 600 imputés sur la facture A (1000) -> reliquat 400 ; facture B intacte.
    assert len(result) == 2
    by_id = {item.source_line_id: item for item in result}
    assert by_id[1].amount_remaining == Decimal("400.00")
    assert by_id[2].amount_remaining == Decimal("400.00")


def test_compte_solde_liste_vide():
    """Compte entièrement soldé : aucune créance résiduelle."""
    lines = [
        _line(1, "2025-02-01", debit="1000.00", label="Facture"),
        _line(2, "2025-02-20", credit="1000.00", label="Paiement"),
    ]

    result = reconcile_account(lines, window_start=date(2025, 1, 1))

    assert result == []


def test_tolerance_arrondi():
    """Un reliquat <= 0,005 € est considéré nul (arrondi) et n'est pas rendu."""
    lines = [
        _line(1, "2025-02-01", debit="1000.00", label="Facture"),
        _line(2, "2025-02-20", credit="999.997", label="Paiement"),
    ]

    result = reconcile_account(lines, window_start=date(2025, 1, 1))

    assert result == []


def test_open_item_est_bien_typed():
    """Le retour est composé d'OpenItem (sanity check de l'API publique)."""
    lines = [_line(1, "2025-02-01", debit="100.00", label="Facture")]
    result = reconcile_account(lines, window_start=date(2025, 1, 1))
    assert all(isinstance(item, OpenItem) for item in result)
