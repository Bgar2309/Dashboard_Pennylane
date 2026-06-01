"""Helpers purs de calcul d'ancienneté et de niveau de relance. Aucun I/O."""
from datetime import date

from .models import AgingBucket, ReminderLevel, ReminderLogEntry


def bucket_for(due_date: date | None, today: date) -> AgingBucket:
    """Bucket d'aging basé sur la date d'échéance (pas la date de facture)."""
    if due_date is None or due_date >= today:
        return AgingBucket.NOT_DUE
    days = (today - due_date).days
    if days <= 30:
        return AgingBucket.D0_30
    if days <= 60:
        return AgingBucket.D30_60
    if days <= 90:
        return AgingBucket.D60_90
    return AgingBucket.D90_PLUS


def level_for(bucket: AgingBucket,
              last_reminder: ReminderLogEntry | None) -> ReminderLevel:
    """Niveau de relance suggéré selon l'ancienneté + dernière relance envoyée.

    Logique simple, ajustable :
      - NOT_DUE / D0_30      → FIRST (ou NONE si pas en retard)
      - D30_60               → SECOND
      - D60_90 / D90_PLUS    → FORMAL
    On monte d'un cran si une relance de même niveau a déjà été envoyée.
    """
    base = {
        AgingBucket.NOT_DUE: ReminderLevel.NONE,
        AgingBucket.D0_30: ReminderLevel.FIRST,
        AgingBucket.D30_60: ReminderLevel.SECOND,
        AgingBucket.D60_90: ReminderLevel.FORMAL,
        AgingBucket.D90_PLUS: ReminderLevel.FORMAL,
    }[bucket]

    if last_reminder is None:
        return base
    order = [ReminderLevel.NONE, ReminderLevel.FIRST,
             ReminderLevel.SECOND, ReminderLevel.FORMAL]
    if order.index(last_reminder.level) >= order.index(base):
        idx = min(order.index(last_reminder.level) + 1, len(order) - 1)
        return order[idx]
    return base
