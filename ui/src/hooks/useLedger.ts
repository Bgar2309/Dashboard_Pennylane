// useLedger — grand livre client agrégé (GET /api/ledger).

import { useCallback } from "react";

import { getLedger, type CustomerDunningRow, type IsoDate } from "../api-client";
import { useAsync, type AsyncState } from "./useAsync";

/** Charge le grand livre client (aging brut, sans banque ni historique). */
export function useLedger(today?: IsoDate): AsyncState<CustomerDunningRow[]> {
  const fetcher = useCallback(
    (signal: AbortSignal) => getLedger(today, signal),
    [today],
  );
  return useAsync(fetcher, [today]);
}
