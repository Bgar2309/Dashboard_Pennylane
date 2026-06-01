// useLedger — grand livre client agrégé (GET /api/ledger).

import { useCallback, useRef } from "react";

import { getLedger, type CustomerDunningRow, type IsoDate } from "../api-client";
import { useAsync, type AsyncState } from "./useAsync";

export interface UseLedgerResult extends AsyncState<CustomerDunningRow[]> {
  /**
   * Relance le fetch en FORÇANT un appel Pennylane frais (`refresh=true`),
   * peu importe l'âge du cache. Distinct du `refresh` normal (qui peut servir
   * le cache backend).
   */
  forceRefresh: () => void;
}

/** Charge le grand livre client (aging brut, sans banque ni historique). */
export function useLedger(today?: IsoDate): UseLedgerResult {
  // Quand vrai, le prochain fetch force le rappel Pennylane (consommé à l'appel).
  const forceRef = useRef(false);

  const fetcher = useCallback(
    (signal: AbortSignal) => {
      const force = forceRef.current;
      forceRef.current = false; // ne force que le fetch déclenché par forceRefresh
      return getLedger(today, force, signal);
    },
    [today],
  );

  const state = useAsync(fetcher, [today]);
  const { refresh } = state;

  const forceRefresh = useCallback(() => {
    forceRef.current = true;
    refresh();
  }, [refresh]);

  return { ...state, forceRefresh };
}
