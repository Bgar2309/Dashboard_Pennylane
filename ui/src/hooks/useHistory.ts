// useHistory — historique des relances loggées (GET /api/reminders/history).

import { useCallback } from "react";

import { getHistory, type ReminderLogEntry } from "../api-client";
import { useAsync, type AsyncState } from "./useAsync";

export interface UseHistoryOptions {
  /** Filtre sur un client précis (sinon tous). */
  customerId?: number;
  /** Nombre max d'entrées (défaut API : 100). */
  limit?: number;
}

/** Charge l'historique des relances (plus récent d'abord). */
export function useHistory(
  options?: UseHistoryOptions,
): AsyncState<ReminderLogEntry[]> {
  const customerId = options?.customerId;
  const limit = options?.limit;
  const fetcher = useCallback(
    (signal: AbortSignal) => getHistory({ customerId, limit }, signal),
    [customerId, limit],
  );
  return useAsync(fetcher, [customerId, limit]);
}
