"""Cœur 'ne jamais relancer un client déjà payé'.
Filtre les transactions, détecte n° de facture, matche en 3 niveaux de confiance.
Ne parse pas les fichiers (hsbc_parser), n'écrit pas dans Pennylane.
"""
from core.models import BankTransaction, Invoice, PaymentMatch
from storage import Storage


class BankMatchService:
    def __init__(self, storage: Storage) -> None:
        raise NotImplementedError

    def is_client_payment(self, tx: BankTransaction) -> bool:
        """True seulement si crédit ET pas interne/frais/TVA (voir filters.py)."""
        raise NotImplementedError

    def extract_invoice_numbers(self, label: str) -> list[str]:
        """Détecte les n° de facture EHS (26xxxx / CA 26xxxxx) dans le libellé."""
        raise NotImplementedError

    def match(self, txs: list[BankTransaction],
              open_invoices: list[Invoice]) -> list[PaymentMatch]:
        """STRONG (n° facture + montant≈) / MEDIUM (nom fuzzy + montant) / WEAK (montant seul)."""
        raise NotImplementedError

    def covered_invoice_ids(self, matches: list[PaymentMatch]) -> set[int]:
        """Ids de factures payées par la banque -> à exclure des relances."""
        raise NotImplementedError
