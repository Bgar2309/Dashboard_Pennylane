"""Schemas Pydantic — miroir JSON sérialisable des dataclasses ``core``.

Construit en 1er dans la vague API : les routers en dépendent. Chaque schéma de
sortie expose un ``from_domain`` qui convertit l'objet ``core`` correspondant.
Aucune logique métier ici : uniquement de la (dé)sérialisation.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from core.models import (AgingBucket, Customer, CustomerDunningRow, Invoice,
                         MatchConfidence, PaymentMatch, ReminderLevel,
                         ReminderLogEntry)


class CustomerOut(BaseModel):
    """Client Pennylane (identité minimale)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None = None

    @classmethod
    def from_domain(cls, c: Customer) -> "CustomerOut":
        return cls(id=c.id, name=c.name, email=c.email)


class InvoiceOut(BaseModel):
    """Facture client (TTC + reste dû)."""
    model_config = ConfigDict(from_attributes=True)

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

    @classmethod
    def from_domain(cls, inv: Invoice) -> "InvoiceOut":
        return cls(
            id=inv.id, number=inv.number, customer_id=inv.customer_id,
            customer_name=inv.customer_name, date=inv.date,
            due_date=inv.due_date, amount=inv.amount, currency=inv.currency,
            paid=inv.paid, remaining_amount=inv.remaining_amount,
        )


class ReminderLogEntryOut(BaseModel):
    """Entrée d'historique : une relance loggée comme envoyée."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    customer_name: str
    level: ReminderLevel
    sent_at: datetime
    invoice_numbers: list[str]
    note: str | None = None

    @classmethod
    def from_domain(cls, e: ReminderLogEntry) -> "ReminderLogEntryOut":
        return cls(
            id=e.id, customer_id=e.customer_id, customer_name=e.customer_name,
            level=e.level, sent_at=e.sent_at,
            invoice_numbers=list(e.invoice_numbers), note=e.note,
        )


class CustomerDunningRowOut(BaseModel):
    """Une ligne du grand livre client agrégée pour la vue relance."""
    model_config = ConfigDict(from_attributes=True)

    customer: CustomerOut
    open_invoices: list[InvoiceOut]
    total_due: Decimal
    oldest_due_date: date | None
    worst_bucket: AgingBucket
    suggested_level: ReminderLevel
    last_reminder: ReminderLogEntryOut | None
    blocked_by_payment: bool

    @classmethod
    def from_domain(cls, row: CustomerDunningRow) -> "CustomerDunningRowOut":
        return cls(
            customer=CustomerOut.from_domain(row.customer),
            open_invoices=[InvoiceOut.from_domain(i) for i in row.open_invoices],
            total_due=row.total_due,
            oldest_due_date=row.oldest_due_date,
            worst_bucket=row.worst_bucket,
            suggested_level=row.suggested_level,
            last_reminder=(ReminderLogEntryOut.from_domain(row.last_reminder)
                           if row.last_reminder is not None else None),
            blocked_by_payment=row.blocked_by_payment,
        )


class PaymentMatchOut(BaseModel):
    """Rapprochement entre une transaction bancaire et une facture."""
    model_config = ConfigDict(from_attributes=True)

    bank_ref: str
    invoice_id: int | None
    invoice_number: str | None
    customer_name: str | None
    amount: Decimal
    confidence: MatchConfidence
    matched_invoice_numbers: list[str]
    reason: str = ""

    @classmethod
    def from_domain(cls, m: PaymentMatch) -> "PaymentMatchOut":
        return cls(
            bank_ref=m.bank_ref, invoice_id=m.invoice_id,
            invoice_number=m.invoice_number, customer_name=m.customer_name,
            amount=m.amount, confidence=m.confidence,
            matched_invoice_numbers=list(m.matched_invoice_numbers),
            reason=m.reason,
        )


class DraftOut(BaseModel):
    """Texte d'un brouillon de relance (généré à la volée, jamais loggé)."""
    customer_id: int
    draft: str


class TopOverdueItem(BaseModel):
    """Un client du top des retardataires (forme produite par StatsService)."""
    customer_id: int
    customer_name: str
    total_due: Decimal
    worst_bucket: str
    oldest_due_date: date | None
    suggested_level: str
    open_invoices_count: int


class StatsOut(BaseModel):
    """KPIs du dashboard (sortie de StatsService.dashboard_kpis + top_overdue)."""
    encours_total: Decimal
    clients_a_relancer: int
    dso_approche: Decimal
    retard_moyen_pondere: Decimal
    total_par_bucket: dict[str, Decimal]
    top_overdue: list[TopOverdueItem]


class ConfirmSentIn(BaseModel):
    """Corps du POST /reminders/{cid}/confirm — déclenche le log d'envoi."""
    level: ReminderLevel
    invoice_numbers: list[str] = Field(default_factory=list)
    note: str | None = None
