"""Orchestrateur de la vue 'relances à faire'.
Combine ledger (aging) + bank_match (blocage paiement) + storage (historique).

RÈGLE CRITIQUE : generate_draft n'écrit RIEN. Seul confirm_sent loggue dans la DB
(appelé quand Bruno clique 'J'ai envoyé cette relance').
"""
import logging
from datetime import date

from core import level_for
from core.models import (BankTransaction, CustomerDunningRow, ReminderLevel,
                         ReminderLogEntry)
from service.bank_match import BankMatchService
from service.ledger import LedgerService
from service.reminders.drafts import DraftGenerator
from storage import Storage

logger = logging.getLogger(__name__)


class ReminderService:
    """Affine la vue d'aging du ledger avec la banque et l'historique.

    - ``ledger`` fournit l'aging brut (``build_dunning_rows``) et les factures
      ouvertes ; il porte aussi le client Pennylane d'où l'on tire les
      transactions Revolut (comptes liés à Pennylane).
    - ``bank_match`` dit quelles factures sont déjà couvertes par un paiement.
    - ``storage`` est la mémoire des relances déjà envoyées (lecture ici,
      écriture UNIQUEMENT dans ``confirm_sent``).
    - ``drafts`` rend le texte des brouillons (aucun I/O).
    """

    def __init__(self, ledger: LedgerService, bank_match: BankMatchService,
                 storage: Storage, drafts: DraftGenerator) -> None:
        self._ledger = ledger
        self._bank_match = bank_match
        self._storage = storage
        self._drafts = drafts

    def dunning_view(self, today: date,
                     hsbc_txs: list[BankTransaction] | None = None,
                     min_days_between_reminders: int = 8) -> list[CustomerDunningRow]:
        """Aging + blocage paiement (HSBC+Revolut) + historique (anti-spam).

        Part de l'aging brut du ledger, puis :
          - marque ``blocked_by_payment`` les clients dont une facture est déjà
            couverte par un paiement (matchs HSBC passés + Revolut via Pennylane) ;
          - renseigne ``last_reminder`` et recalcule ``suggested_level`` en tenant
            compte de l'historique ;
          - masque les clients relancés depuis moins de
            ``min_days_between_reminders`` jours (anti-spam temporel).
        """
        rows = self._ledger.build_dunning_rows(today)

        # Toutes les factures ouvertes connues, pour donner du contexte au matching.
        open_invoices = [inv for row in rows for inv in row.open_invoices]

        # Frontière HSBC : jusqu'à cette date le lettrage comptable est fiable et
        # les paiements sont déjà reflétés dans l'encours (lignes 411 lettrées,
        # donc absentes). On purge les matchs absorbés et on ignore les virements
        # HSBC manuels antérieurs pour ne pas les rejouer.
        boundary = self._hsbc_boundary()
        purged = (self._storage.clear_matches_before(boundary)
                  if boundary is not None else 0)
        logger.info("Frontière HSBC = %s, %d matchs purgés", boundary, purged)

        # Transactions à croiser : virements HSBC manuels POSTÉRIEURS à la
        # frontière (les antérieurs sont déjà absorbés par le lettrage) + Revolut.
        txs = [tx for tx in (hsbc_txs or [])
               if boundary is None or tx.value_date > boundary]
        txs.extend(self._revolut_transactions())

        matches = self._bank_match.match(txs, open_invoices)
        covered = self._bank_match.covered_invoice_ids(matches)

        view: list[CustomerDunningRow] = []
        for row in rows:
            row.blocked_by_payment = any(inv.id in covered
                                         for inv in row.open_invoices)
            row.last_reminder = self._storage.get_last_reminder(row.customer.id)
            row.suggested_level = level_for(row.worst_bucket, row.last_reminder)

            if self._recently_reminded(row, today, min_days_between_reminders):
                continue  # masqué : on vient de relancer ce client

            view.append(row)
        return view

    def generate_draft(self, customer_id: int, today: date) -> str:
        """TEXTE du brouillon. NE LOGUE RIEN (lecture seule de l'historique)."""
        row = self._row_for(customer_id, today)
        if row is None:
            raise ValueError(f"Aucune facture ouverte pour le client {customer_id}")

        last = self._storage.get_last_reminder(customer_id)
        level = level_for(row.worst_bucket, last)
        return self._drafts.render(row.customer, row.open_invoices, level, today)

    def confirm_sent(self, customer_id: int, level: ReminderLevel,
                     invoice_numbers: list[str], note: str | None = None) -> ReminderLogEntry:
        """SEULE méthode qui écrit dans reminders_log."""
        return self._storage.log_reminder(
            customer_id=customer_id,
            customer_name=self._customer_name(customer_id),
            level=level,
            invoice_numbers=invoice_numbers,
            note=note,
        )

    # ------------------------------------------------------------------ #
    # Internes
    # ------------------------------------------------------------------ #
    def _hsbc_boundary(self) -> date | None:
        """Frontière comptable HSBC via Pennylane, ou None (= pas de purge).

        Dégrade proprement : si le ledger n'expose pas de client Pennylane, que
        celui-ci n'a pas la méthode, ou qu'elle échoue, on rend None et aucune
        purge n'est faite.
        """
        pennylane = getattr(self._ledger, "_pennylane", None)
        getter = getattr(pennylane, "hsbc_accounting_boundary", None)
        if getter is None:
            return None
        try:
            return getter()
        except Exception:  # le réseau ne doit jamais casser la vue relance
            logger.warning("Frontière HSBC indisponible", exc_info=True)
            return None

    def _revolut_transactions(self) -> list[BankTransaction]:
        """Transactions des comptes liés à Pennylane (Revolut), via le ledger.

        Le ledger porte le client Pennylane ; s'il n'expose rien (ou échoue),
        on dégrade proprement vers une absence de transactions Revolut.
        """
        pennylane = getattr(self._ledger, "_pennylane", None)
        if pennylane is None:
            return []
        return list(pennylane.list_bank_transactions())

    def _recently_reminded(self, row: CustomerDunningRow, today: date,
                           min_days: int) -> bool:
        """Vrai si on a relancé ce client depuis moins de ``min_days`` jours."""
        last = row.last_reminder
        if last is None:
            return False
        return (today - last.sent_at.date()).days < min_days

    def _row_for(self, customer_id: int, today: date) -> CustomerDunningRow | None:
        for row in self._ledger.build_dunning_rows(today):
            if row.customer.id == customer_id:
                return row
        return None

    def _customer_name(self, customer_id: int) -> str:
        """Nom du client depuis les factures ouvertes (sans dépendre de ``today``)."""
        for inv in self._ledger.get_open_invoices():
            if inv.customer_id == customer_id:
                return inv.customer_name
        return ""
