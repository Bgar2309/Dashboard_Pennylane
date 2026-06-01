"""Router ledger — grand livre client (lecture).

GET /api/ledger                → grand livre client agrégé (CustomerDunningRow[])
GET /api/ledger/{customer_id}  → factures ouvertes d'un client

Validation -> LedgerService -> sérialisation. Zéro logique métier.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_ledger_service
from api.schemas import CustomerDunningRowOut, InvoiceOut
from service.ledger import LedgerService

router = APIRouter(prefix="/api/ledger", tags=["ledger"])


@router.get("", response_model=list[CustomerDunningRowOut])
def get_ledger(
    today: date | None = None,
    ledger: LedgerService = Depends(get_ledger_service),
) -> list[CustomerDunningRowOut]:
    """Grand livre client agrégé (aging brut, sans banque ni historique)."""
    rows = ledger.build_dunning_rows(today or date.today())
    return [CustomerDunningRowOut.from_domain(r) for r in rows]


@router.get("/{customer_id}", response_model=list[InvoiceOut])
def get_customer_invoices(
    customer_id: int,
    ledger: LedgerService = Depends(get_ledger_service),
) -> list[InvoiceOut]:
    """Factures ouvertes d'un client. 404 si le client n'a aucune facture ouverte."""
    invoices = [inv for inv in ledger.get_open_invoices()
                if inv.customer_id == customer_id]
    if not invoices:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Aucune facture ouverte pour le client {customer_id}",
        )
    return [InvoiceOut.from_domain(inv) for inv in invoices]
