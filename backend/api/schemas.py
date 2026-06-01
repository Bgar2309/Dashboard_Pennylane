"""Schemas Pydantic — miroir JSON des dataclasses ``core``, sérialisables.

Construits en premier dans la vague API : routers et UI s'appuient dessus.
Les énumérations sont réutilisées directement depuis ``core`` (ce sont des
``str`` Enum, donc Pydantic les sérialise nativement).

Conversion depuis les dataclasses ``core`` :
    InvoiceOut.model_validate(invoice)            # objet simple
    CustomerDunningRowOut.model_validate(row)     # validation récursive (nested)
grâce à ``from_attributes=True``.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from core.models import AgingBucket, MatchConfidence, ReminderLevel


class _Base(BaseModel):
    """Base commune : autorise la validation depuis des attributs (dataclasses)."""
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- out
class CustomerOut(_Base):
    id: int
    name: str
    email: str | None = None


class InvoiceOut(_Base):
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


class ReminderLogEntryOut(_Base):
    id: int
    customer_id: int
    customer_name: str
    level: ReminderLevel
    sent_at: datetime
    invoice_numbers: list[str]
    note: str | None = None


class PaymentMatchOut(_Base):
    bank_ref: str
    invoice_id: int | None
    invoice_number: str | None
    customer_name: str | None
    amount: Decimal
    confidence: MatchConfidence
    matched_invoice_numbers: list[str] = []
    reason: str = ""


class CustomerDunningRowOut(_Base):
    customer: CustomerOut
    open_invoices: list[InvoiceOut]
    total_due: Decimal
    oldest_due_date: date | None
    worst_bucket: AgingBucket
    suggested_level: ReminderLevel
    last_reminder: ReminderLogEntryOut | None
    blocked_by_payment: bool


# ------------------------------------------------------------------------ stats
class TopOverdueOut(_Base):
    customer_id: int
    customer_name: str
    total_due: Decimal
    worst_bucket: AgingBucket
    oldest_due_date: date | None
    suggested_level: ReminderLevel
    open_invoices_count: int


class StatsOut(_Base):
    """KPIs du dashboard (miroir de ``StatsService.dashboard_kpis`` + top liste)."""
    encours_total: Decimal
    clients_a_relancer: int
    dso_approche: Decimal
    retard_moyen_pondere: Decimal
    total_par_bucket: dict[str, Decimal]
    top_overdue: list[TopOverdueOut] = []


# --------------------------------------------------------------------------- in
class ConfirmSentIn(BaseModel):
    """Corps du POST /api/reminders/{cid}/confirm — SEUL déclencheur de log."""
    level: ReminderLevel
    invoice_numbers: list[str]
    note: str | None = None
