"""Router bank — rapprochement bancaire HSBC.

POST /api/bank/upload   → fichier HSBC (xlsx/pdf) multipart : parse + match + persiste
GET  /api/bank/matches  → derniers matchs calculés

Le parsing est délégué à ``hsbc_parser`` puis ``bank_match`` (exception assumée :
seul endpoint qui touche ``integration`` en direct, cf. ARCHITECTURE.md).
Zéro logique métier ici.
"""
from __future__ import annotations

from datetime import date

from fastapi import (APIRouter, Depends, File, HTTPException, UploadFile,
                     status)

from api.deps import get_bank_match_service, get_ledger_service, get_storage
from api.schemas import PaymentMatchOut
from integration.hsbc_parser import parse_hsbc
from service.bank_match import BankMatchService
from service.ledger import LedgerService
from storage import Storage

router = APIRouter(prefix="/api/bank", tags=["bank"])

_ALLOWED_EXTENSIONS = (".xlsx", ".xls", ".pdf")


@router.post("/upload", response_model=list[PaymentMatchOut],
             status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    bank_match: BankMatchService = Depends(get_bank_match_service),
    ledger: LedgerService = Depends(get_ledger_service),
    storage: Storage = Depends(get_storage),
) -> list[PaymentMatchOut]:
    """Parse un relevé HSBC, le rapproche des factures ouvertes, persiste les matchs."""
    filename = file.filename or ""
    if not filename.lower().endswith(_ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format non supporté : {filename!r} (attendu : xlsx/xls/pdf)",
        )

    file_bytes = await file.read()
    try:
        txs = parse_hsbc(file_bytes, filename)
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Relevé HSBC illisible : {exc}",
        ) from exc

    open_invoices = ledger.get_open_invoices()
    matches = bank_match.match(txs, open_invoices)
    storage.save_matches(matches)
    return [PaymentMatchOut.from_domain(m) for m in matches]


@router.get("/matches", response_model=list[PaymentMatchOut])
def get_matches(
    since: date | None = None,
    storage: Storage = Depends(get_storage),
) -> list[PaymentMatchOut]:
    """Derniers matchs calculés (plus récent d'abord), optionnellement depuis une date."""
    matches = storage.list_matches(since=since)
    return [PaymentMatchOut.from_domain(m) for m in matches]
