"""Router stats — KPIs du dashboard.

GET /api/stats → encours, DSO, retard moyen, répartition aging, top retardataires.

Les lignes d'aging proviennent du ledger (porté par StatsService) ; StatsService
les agrège. Zéro logique métier dans le router.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from api.deps import get_stats_service
from api.schemas import StatsOut
from service.stats import StatsService

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsOut)
def get_stats(
    today: date | None = None,
    stats: StatsService = Depends(get_stats_service),
) -> StatsOut:
    """KPIs dashboard calculés sur le grand livre client agrégé."""
    day = today or date.today()
    rows = stats.ledger.build_dunning_rows(day)
    kpis = stats.dashboard_kpis(rows, day)
    return StatsOut(**kpis, top_overdue=stats.top_overdue(rows))
