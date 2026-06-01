"""Router reminders — vue relances, brouillons, confirmation, historique.

GET  /api/reminders               → vue relances à faire (blocage banque + anti-spam)
GET  /api/reminders/history       → historique des relances loggées
GET  /api/reminders/{cid}/draft   → texte du brouillon (NE LOGUE RIEN)
POST /api/reminders/{cid}/confirm → log d'envoi (SEUL point d'écriture de l'historique)

Validation -> ReminderService / Storage -> sérialisation. Zéro logique métier.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_reminder_service, get_storage
from api.schemas import (ConfirmSentIn, CustomerDunningRowOut, DraftOut,
                         ReminderLogEntryOut)
from service.reminders.service import ReminderService
from storage import Storage

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


@router.get("", response_model=list[CustomerDunningRowOut])
def get_reminders(
    today: date | None = None,
    refresh: bool = False,
    reminders: ReminderService = Depends(get_reminder_service),
) -> list[CustomerDunningRowOut]:
    """Vue relances à faire : aging + blocage paiement + historique (anti-spam).

    ``refresh=true`` force un appel Pennylane frais (bypass du cache).
    """
    rows = reminders.dunning_view(today or date.today(), refresh=refresh)
    return [CustomerDunningRowOut.from_domain(r) for r in rows]


@router.get("/history", response_model=list[ReminderLogEntryOut])
def get_history(
    customer_id: int | None = None,
    limit: int = 100,
    storage: Storage = Depends(get_storage),
) -> list[ReminderLogEntryOut]:
    """Historique des relances loggées (plus récent d'abord)."""
    entries = storage.list_reminders(customer_id=customer_id, limit=limit)
    return [ReminderLogEntryOut.from_domain(e) for e in entries]


@router.get("/{customer_id}/draft", response_model=DraftOut)
def get_draft(
    customer_id: int,
    today: date | None = None,
    reminders: ReminderService = Depends(get_reminder_service),
) -> DraftOut:
    """Texte du brouillon de relance. Lecture seule : n'écrit jamais l'historique."""
    try:
        text = reminders.generate_draft(customer_id, today or date.today())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return DraftOut(customer_id=customer_id, draft=text)


@router.post("/{customer_id}/confirm", response_model=ReminderLogEntryOut,
             status_code=status.HTTP_201_CREATED)
def confirm_sent(
    customer_id: int,
    payload: ConfirmSentIn,
    reminders: ReminderService = Depends(get_reminder_service),
) -> ReminderLogEntryOut:
    """Confirme l'envoi d'une relance → log dans l'historique (SEUL point d'écriture)."""
    entry = reminders.confirm_sent(
        customer_id=customer_id,
        level=payload.level,
        invoice_numbers=payload.invoice_numbers,
        note=payload.note,
    )
    return ReminderLogEntryOut.from_domain(entry)
