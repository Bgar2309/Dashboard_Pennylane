// useStats — KPIs du dashboard (GET /api/stats).

import { useCallback } from "react";

import { getStats, type IsoDate, type Stats } from "../api-client";
import { useAsync, type AsyncState } from "./useAsync";

/** Charge les KPIs : encours, DSO, retard moyen, aging, top retardataires. */
export function useStats(today?: IsoDate): AsyncState<Stats> {
  const fetcher = useCallback(
    (signal: AbortSignal) => getStats(today, signal),
    [today],
  );
  return useAsync(fetcher, [today]);
}
