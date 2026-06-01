"""Persistance SQLite : historique relances, matchs de paiement, cache factures.
Aucune logique métier, aucun appel réseau. Stocke et rend.
"""
from datetime import date, datetime

from core.models import (Invoice, PaymentMatch, ReminderLevel, ReminderLogEntry)


class Storage:
    def __init__(self, db_path: str | None = None) -> None:
        # TODO: db_path depuis env DATABASE_PATH, défaut /data/relance.db
        raise NotImplementedError

    def init_schema(self) -> None:
        # TODO: CREATE TABLE reminders_log, payment_matches, invoice_cache, cache_meta
        raise NotImplementedError

    # --- Historique relances (écrit UNIQUEMENT via log_reminder, sur confirmation) ---
    def log_reminder(self, customer_id: int, customer_name: str,
                     level: ReminderLevel, invoice_numbers: list[str],
                     note: str | None = None) -> ReminderLogEntry:
        raise NotImplementedError

    def get_last_reminder(self, customer_id: int) -> ReminderLogEntry | None:
        raise NotImplementedError

    def list_reminders(self, customer_id: int | None = None,
                       limit: int = 100) -> list[ReminderLogEntry]:
        raise NotImplementedError

    # --- Matchs de paiement ---
    def save_matches(self, matches: list[PaymentMatch]) -> None:
        raise NotImplementedError

    def list_matches(self, since: date | None = None) -> list[PaymentMatch]:
        raise NotImplementedError

    def clear_matches(self) -> None:
        raise NotImplementedError

    # --- Cache factures ---
    def cache_invoices(self, invoices: list[Invoice]) -> None:
        raise NotImplementedError

    def get_cached_invoices(self) -> list[Invoice]:
        raise NotImplementedError

    def cache_age_seconds(self) -> float | None:
        raise NotImplementedError
