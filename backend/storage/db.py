"""Persistance SQLite : historique relances, matchs de paiement, cache factures.
Aucune logique métier, aucun appel réseau. Stocke et rend.

Tables : reminders_log, payment_matches, invoice_cache, cache_meta.
Les listes de numéros de facture sont sérialisées en JSON ; les montants Decimal
sont stockés en texte pour préserver la précision.
"""
import json
import os
import sqlite3
from datetime import date, datetime
from decimal import Decimal

import config
from core.models import (Invoice, MatchConfidence, PaymentMatch,
                         ReminderLevel, ReminderLogEntry)

# Clé du cache_meta : horodatage du dernier remplissage du cache factures.
_CACHE_TS_KEY = "invoices_cached_at"


class Storage:
    """Couche de persistance SQLite. Stocke et rend, sans logique métier."""

    def __init__(self, db_path: str | None = None) -> None:
        """db_path explicite, sinon config.DATABASE_PATH (env DATABASE_PATH)."""
        self.db_path = db_path if db_path is not None else config.DATABASE_PATH
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # check_same_thread=False : la même instance peut être partagée entre
        # threads (singleton FastAPI). Les écritures restent sérialisées par SQLite.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        """Crée les tables si absentes. Idempotent."""
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reminders_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id     INTEGER NOT NULL,
                customer_name   TEXT    NOT NULL,
                level           TEXT    NOT NULL,
                sent_at         TEXT    NOT NULL,
                invoice_numbers TEXT    NOT NULL,
                note            TEXT
            );

            CREATE TABLE IF NOT EXISTS payment_matches (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_ref                TEXT    NOT NULL,
                invoice_id              INTEGER,
                invoice_number          TEXT,
                customer_name           TEXT,
                amount                  TEXT    NOT NULL,
                confidence              TEXT    NOT NULL,
                matched_invoice_numbers TEXT    NOT NULL,
                reason                  TEXT    NOT NULL DEFAULT '',
                created_at              TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS invoice_cache (
                id               INTEGER PRIMARY KEY,
                number           TEXT    NOT NULL,
                customer_id      INTEGER NOT NULL,
                customer_name    TEXT    NOT NULL,
                date             TEXT    NOT NULL,
                due_date         TEXT,
                amount           TEXT    NOT NULL,
                currency         TEXT    NOT NULL,
                paid             INTEGER NOT NULL,
                remaining_amount TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cache_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_reminders_customer
                ON reminders_log (customer_id, id);
            """
        )
        self._conn.commit()

    # --- Historique relances (écrit UNIQUEMENT via log_reminder, sur confirmation) ---
    def log_reminder(self, customer_id: int, customer_name: str,
                     level: ReminderLevel, invoice_numbers: list[str],
                     note: str | None = None) -> ReminderLogEntry:
        """Enregistre une relance envoyée. SEUL point d'écriture de l'historique."""
        sent_at = datetime.now()
        cur = self._conn.execute(
            """INSERT INTO reminders_log
               (customer_id, customer_name, level, sent_at, invoice_numbers, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (customer_id, customer_name, level.value, sent_at.isoformat(),
             json.dumps(invoice_numbers), note),
        )
        self._conn.commit()
        return ReminderLogEntry(
            id=cur.lastrowid,
            customer_id=customer_id,
            customer_name=customer_name,
            level=level,
            sent_at=sent_at,
            invoice_numbers=list(invoice_numbers),
            note=note,
        )

    def get_last_reminder(self, customer_id: int) -> ReminderLogEntry | None:
        """Dernière relance loggée pour un client, ou None."""
        row = self._conn.execute(
            "SELECT * FROM reminders_log WHERE customer_id = ? ORDER BY id DESC LIMIT 1",
            (customer_id,),
        ).fetchone()
        return self._row_to_reminder(row) if row is not None else None

    def list_reminders(self, customer_id: int | None = None,
                       limit: int = 100) -> list[ReminderLogEntry]:
        """Historique (plus récent d'abord). Filtré par client si fourni."""
        if customer_id is None:
            rows = self._conn.execute(
                "SELECT * FROM reminders_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM reminders_log WHERE customer_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (customer_id, limit),
            ).fetchall()
        return [self._row_to_reminder(r) for r in rows]

    # --- Matchs de paiement ---
    def save_matches(self, matches: list[PaymentMatch]) -> None:
        """Ajoute des matchs calculés (n'efface pas l'existant : voir clear_matches)."""
        created_at = datetime.now().isoformat()
        self._conn.executemany(
            """INSERT INTO payment_matches
               (bank_ref, invoice_id, invoice_number, customer_name, amount,
                confidence, matched_invoice_numbers, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(m.bank_ref, m.invoice_id, m.invoice_number, m.customer_name,
              str(m.amount), m.confidence.value,
              json.dumps(m.matched_invoice_numbers), m.reason, created_at)
             for m in matches],
        )
        self._conn.commit()

    def list_matches(self, since: date | None = None) -> list[PaymentMatch]:
        """Matchs enregistrés (plus récent d'abord), optionnellement depuis une date."""
        if since is None:
            rows = self._conn.execute(
                "SELECT * FROM payment_matches ORDER BY id DESC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM payment_matches WHERE created_at >= ? ORDER BY id DESC",
                (since.isoformat(),),
            ).fetchall()
        return [self._row_to_match(r) for r in rows]

    def clear_matches(self) -> None:
        """Vide la table des matchs de paiement."""
        self._conn.execute("DELETE FROM payment_matches")
        self._conn.commit()

    # --- Cache factures ---
    def cache_invoices(self, invoices: list[Invoice]) -> None:
        """Remplace intégralement le cache factures et met à jour l'horodatage."""
        self._conn.execute("DELETE FROM invoice_cache")
        self._conn.executemany(
            """INSERT INTO invoice_cache
               (id, number, customer_id, customer_name, date, due_date, amount,
                currency, paid, remaining_amount)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(inv.id, inv.number, inv.customer_id, inv.customer_name,
              inv.date.isoformat(),
              inv.due_date.isoformat() if inv.due_date is not None else None,
              str(inv.amount), inv.currency, 1 if inv.paid else 0,
              str(inv.remaining_amount))
             for inv in invoices],
        )
        self._conn.execute(
            "INSERT INTO cache_meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_CACHE_TS_KEY, datetime.now().isoformat()),
        )
        self._conn.commit()

    def get_cached_invoices(self) -> list[Invoice]:
        """Factures en cache (liste vide si cache jamais rempli)."""
        rows = self._conn.execute(
            "SELECT * FROM invoice_cache ORDER BY id"
        ).fetchall()
        return [self._row_to_invoice(r) for r in rows]

    def cache_age_seconds(self) -> float | None:
        """Âge du cache factures en secondes, ou None si jamais rempli."""
        row = self._conn.execute(
            "SELECT value FROM cache_meta WHERE key = ?", (_CACHE_TS_KEY,)
        ).fetchone()
        if row is None:
            return None
        cached_at = datetime.fromisoformat(row["value"])
        return (datetime.now() - cached_at).total_seconds()

    def close(self) -> None:
        """Ferme la connexion SQLite."""
        self._conn.close()

    # --- Helpers de désérialisation (privés) ---
    @staticmethod
    def _row_to_reminder(row: sqlite3.Row) -> ReminderLogEntry:
        return ReminderLogEntry(
            id=row["id"],
            customer_id=row["customer_id"],
            customer_name=row["customer_name"],
            level=ReminderLevel(row["level"]),
            sent_at=datetime.fromisoformat(row["sent_at"]),
            invoice_numbers=json.loads(row["invoice_numbers"]),
            note=row["note"],
        )

    @staticmethod
    def _row_to_match(row: sqlite3.Row) -> PaymentMatch:
        return PaymentMatch(
            bank_ref=row["bank_ref"],
            invoice_id=row["invoice_id"],
            invoice_number=row["invoice_number"],
            customer_name=row["customer_name"],
            amount=Decimal(row["amount"]),
            confidence=MatchConfidence(row["confidence"]),
            matched_invoice_numbers=json.loads(row["matched_invoice_numbers"]),
            reason=row["reason"],
        )

    @staticmethod
    def _row_to_invoice(row: sqlite3.Row) -> Invoice:
        return Invoice(
            id=row["id"],
            number=row["number"],
            customer_id=row["customer_id"],
            customer_name=row["customer_name"],
            date=date.fromisoformat(row["date"]),
            due_date=date.fromisoformat(row["due_date"]) if row["due_date"] else None,
            amount=Decimal(row["amount"]),
            currency=row["currency"],
            paid=bool(row["paid"]),
            remaining_amount=Decimal(row["remaining_amount"]),
        )
