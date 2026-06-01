"""Wrapper REST Pennylane v2, LECTURE SEULE. Seul module qui parle à Pennylane.
Traduit le JSON Pennylane en objets core. Aucun push (create/update/delete).

AVANT DE CODER : lire https://pennylane.readme.io/reference pour les champs exacts.
Auth: header Authorization: Bearer <PENNYLANE_TOKEN>. Tout paginer (cursor/has_more).
"""
from datetime import date

from core.models import BankTransaction, Customer, Invoice


class PennylaneClient:
    def __init__(self, token: str | None = None,
                 base_url: str = "https://app.pennylane.com/api/external/v2") -> None:
        # TODO: token depuis env PENNYLANE_TOKEN si None
        raise NotImplementedError

    def list_customers(self) -> list[Customer]:
        raise NotImplementedError

    def list_open_invoices(self) -> list[Invoice]:
        """Factures clients non soldées (remaining_amount > 0). Pagine tout."""
        raise NotImplementedError

    def list_all_invoices(self, since: date | None = None) -> list[Invoice]:
        raise NotImplementedError

    def get_invoice(self, invoice_id: int) -> Invoice:
        raise NotImplementedError

    def list_bank_transactions(self, since: date | None = None) -> list[BankTransaction]:
        """Transactions des comptes liés à Pennylane (Revolut). source='revolut'."""
        raise NotImplementedError
