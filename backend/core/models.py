"""Modèles de données partagés. Aucune dépendance, aucun I/O.

Tous les modules importent depuis ici. Ne JAMAIS ajouter de logique réseau/DB.
Les helpers purs (bucket_for, level_for) sont dans core/aging.py.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class ReminderLevel(str, Enum):
    NONE = "none"        # pas encore en retard
    FIRST = "first"      # 1ère relance (douce)
    SECOND = "second"    # 2ème relance (ferme)
    FORMAL = "formal"    # mise en demeure


class AgingBucket(str, Enum):
    NOT_DUE = "not_due"
    D0_30 = "0-30"
    D30_60 = "30-60"
    D60_90 = "60-90"
    D90_PLUS = "90+"


class MatchConfidence(str, Enum):
    STRONG = "strong"   # n° facture 26xxxx trouvé + montant ≈
    MEDIUM = "medium"   # nom client fuzzy + montant exact
    WEAK = "weak"       # montant exact seul, fenêtre de date
    NONE = "none"


@dataclass
class Customer:
    id: int
    name: str
    email: str | None = None


@dataclass
class Invoice:
    id: int
    number: str
    customer_id: int
    customer_name: str
    date: date
    due_date: date | None
    amount: Decimal
    currency: str
    paid: bool
    remaining_amount: Decimal


@dataclass
class BankTransaction:
    ref: str
    value_date: date
    op_date: date | None
    label: str
    client_ref: str | None
    credit: Decimal | None
    debit: Decimal | None
    source: str = "hsbc"  # "hsbc" | "revolut"


@dataclass
class PaymentMatch:
    bank_ref: str
    invoice_id: int | None
    invoice_number: str | None
    customer_name: str | None
    amount: Decimal
    confidence: MatchConfidence
    matched_invoice_numbers: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class ReminderLogEntry:
    id: int
    customer_id: int
    customer_name: str
    level: ReminderLevel
    sent_at: datetime
    invoice_numbers: list[str]
    note: str | None = None


@dataclass
class CustomerDunningRow:
    customer: Customer
    open_invoices: list[Invoice]
    total_due: Decimal
    oldest_due_date: date | None
    worst_bucket: AgingBucket
    suggested_level: ReminderLevel
    last_reminder: ReminderLogEntry | None
    blocked_by_payment: bool
