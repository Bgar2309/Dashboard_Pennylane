"""Orchestrateur de la vue 'relances à faire'.
Combine ledger (aging) + bank_match (blocage paiement) + storage (historique).

RÈGLE CRITIQUE : generate_draft n'écrit RIEN. Seul confirm_sent loggue dans la DB
(appelé quand Bruno clique 'J'ai envoyé cette relance').
"""
from datetime import date

from core.models import (BankTransaction, CustomerDunningRow, ReminderLevel,
                         ReminderLogEntry)
from service.bank_match import BankMatchService
from service.ledger import LedgerService
from service.reminders.drafts import DraftGenerator
from storage import Storage


class ReminderService:
    def __init__(self, ledger: LedgerService, bank_match: BankMatchService,
                 storage: Storage, drafts: DraftGenerator) -> None:
        raise NotImplementedError

    def dunning_view(self, today: date,
                     hsbc_txs: list[BankTransaction] | None = None,
                     min_days_between_reminders: int = 8) -> list[CustomerDunningRow]:
        """Aging + blocage paiement (HSBC+Revolut) + historique (anti-spam)."""
        raise NotImplementedError

    def generate_draft(self, customer_id: int, today: date) -> str:
        """TEXTE du brouillon. NE LOGUE RIEN."""
        raise NotImplementedError

    def confirm_sent(self, customer_id: int, level: ReminderLevel,
                     invoice_numbers: list[str], note: str | None = None) -> ReminderLogEntry:
        """SEULE méthode qui écrit dans reminders_log."""
        raise NotImplementedError
