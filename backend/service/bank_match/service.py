"""Cœur 'ne jamais relancer un client déjà payé'.
Filtre les transactions, détecte n° de facture, matche en 3 niveaux de confiance.
Ne parse pas les fichiers (hsbc_parser), n'écrit pas dans Pennylane.
"""
import re
from decimal import Decimal

from rapidfuzz import fuzz

from core.models import (BankTransaction, Invoice, MatchConfidence,
                         PaymentMatch)
from storage import Storage

from . import filters

# Seuil de similarité du nom client (rapidfuzz) pour un match MEDIUM.
_FUZZY_THRESHOLD = 85
# Tolérance montant pour un match STRONG : ±1% OU ±1€ (le plus permissif des deux).
_AMOUNT_PCT = Decimal("0.01")
_AMOUNT_ABS = Decimal("1")

_INVOICE_RE = re.compile(filters.INVOICE_NUMBER_REGEX)


def _normalize(text: str) -> str:
    """Majuscules sans espaces : comparaison insensible à la casse/aux espaces."""
    return "".join(text.split()).upper()


class BankMatchService:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def is_client_payment(self, tx: BankTransaction) -> bool:
        """True seulement si crédit ET pas interne/frais/TVA (voir filters.py)."""
        if tx.credit is None or tx.credit <= 0:
            return False
        label = _normalize(tx.label)
        for pattern in filters.INTERNAL_LABELS + filters.FEE_LABELS:
            if _normalize(pattern) in label:
                return False
        return True

    def extract_invoice_numbers(self, label: str) -> list[str]:
        """Détecte les n° de facture EHS (26xxxx / CA 26xxxxx) dans le libellé."""
        return _INVOICE_RE.findall(label)

    def match(self, txs: list[BankTransaction],
              open_invoices: list[Invoice]) -> list[PaymentMatch]:
        """STRONG (n° facture + montant≈) / MEDIUM (nom fuzzy + montant) / WEAK (montant seul)."""
        matches: list[PaymentMatch] = []
        for tx in txs:
            if not self.is_client_payment(tx):
                continue
            matches.append(self._match_one(tx, open_invoices))
        return matches

    def _match_one(self, tx: BankTransaction,
                   open_invoices: list[Invoice]) -> PaymentMatch:
        amount = tx.credit  # garanti non None / positif par is_client_payment
        numbers = self.extract_invoice_numbers(tx.label)

        strong = self._find_strong(amount, numbers, open_invoices)
        if strong is not None:
            return PaymentMatch(
                bank_ref=tx.ref, invoice_id=strong.id,
                invoice_number=strong.number, customer_name=strong.customer_name,
                amount=amount, confidence=MatchConfidence.STRONG,
                matched_invoice_numbers=numbers,
                reason=(f"N° facture {strong.number} trouvé dans le libellé "
                        f"et montant {amount} ≈ {strong.amount} (±1% ou ±1€)"),
            )

        medium = self._find_medium(tx.label, amount, open_invoices)
        if medium is not None:
            inv, score = medium
            return PaymentMatch(
                bank_ref=tx.ref, invoice_id=inv.id,
                invoice_number=inv.number, customer_name=inv.customer_name,
                amount=amount, confidence=MatchConfidence.MEDIUM,
                matched_invoice_numbers=numbers,
                reason=(f"Nom client « {inv.customer_name} » similaire "
                        f"(fuzzy {score:.0f} ≥ {_FUZZY_THRESHOLD}) "
                        f"et montant exact {amount}"),
            )

        weak = self._find_weak(amount, open_invoices)
        if weak is not None:
            return PaymentMatch(
                bank_ref=tx.ref, invoice_id=weak.id,
                invoice_number=weak.number, customer_name=weak.customer_name,
                amount=amount, confidence=MatchConfidence.WEAK,
                matched_invoice_numbers=numbers,
                reason=(f"Montant exact {amount} seul "
                        f"(aucun n° de facture ni nom client concordant)"),
            )

        return PaymentMatch(
            bank_ref=tx.ref, invoice_id=None, invoice_number=None,
            customer_name=None, amount=amount, confidence=MatchConfidence.NONE,
            matched_invoice_numbers=numbers,
            reason=f"Aucune facture ouverte ne correspond au montant {amount}",
        )

    @staticmethod
    def _amount_close(a: Decimal, b: Decimal) -> bool:
        """Montants proches : écart ≤ 1€ OU ≤ 1% du montant facturé."""
        diff = abs(a - b)
        return diff <= _AMOUNT_ABS or diff <= abs(b) * _AMOUNT_PCT

    def _find_strong(self, amount: Decimal, numbers: list[str],
                     invoices: list[Invoice]) -> Invoice | None:
        if not numbers:
            return None
        wanted = set(numbers)
        for inv in invoices:
            if inv.number in wanted and self._amount_close(amount, inv.amount):
                return inv
        return None

    @staticmethod
    def _find_medium(label: str, amount: Decimal,
                     invoices: list[Invoice]) -> tuple[Invoice, float] | None:
        best: tuple[Invoice, float] | None = None
        label_up = label.upper()
        for inv in invoices:
            if amount != inv.amount:
                continue
            score = fuzz.partial_ratio(inv.customer_name.upper(), label_up)
            if score >= _FUZZY_THRESHOLD and (best is None or score > best[1]):
                best = (inv, score)
        return best

    @staticmethod
    def _find_weak(amount: Decimal, invoices: list[Invoice]) -> Invoice | None:
        for inv in invoices:
            if amount == inv.amount:
                return inv
        return None

    def covered_invoice_ids(self, matches: list[PaymentMatch]) -> set[int]:
        """Ids de factures payées par la banque -> à exclure des relances."""
        covered = {MatchConfidence.STRONG, MatchConfidence.MEDIUM}
        return {
            m.invoice_id for m in matches
            if m.invoice_id is not None and m.confidence in covered
        }
