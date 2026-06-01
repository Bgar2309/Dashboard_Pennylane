// useReminders — vue relances à faire (GET /api/reminders) + actions
// brouillon / confirmation d'envoi.

import { useCallback, useRef, useState } from "react";

import {
  confirmSent as apiConfirmSent,
  getDraft as apiGetDraft,
  getReminders,
  type ConfirmSentIn,
  type CustomerDunningRow,
  type Draft,
  type IsoDate,
  type ReminderLogEntry,
} from "../api-client";
import { useAsync, type AsyncState } from "./useAsync";

export interface UseRemindersResult extends AsyncState<CustomerDunningRow[]> {
  /** Récupère le texte du brouillon d'un client (ne logue rien). */
  fetchDraft: (customerId: number) => Promise<Draft>;
  /** Confirme l'envoi → log d'historique, puis rafraîchit la vue. */
  confirmSent: (
    customerId: number,
    body: ConfirmSentIn,
  ) => Promise<ReminderLogEntry>;
  /** Vrai pendant un appel `confirmSent`. */
  confirming: boolean;
  /**
   * Relance le fetch en FORÇANT un appel Pennylane frais (`refresh=true`),
   * peu importe l'âge du cache. Distinct du `refresh` normal (qui peut servir
   * le cache backend).
   */
  forceRefresh: () => void;
}

/** Vue relances : aging + blocage paiement + anti-spam, avec actions. */
export function useReminders(today?: IsoDate): UseRemindersResult {
  // Quand vrai, le prochain fetch force le rappel Pennylane (consommé à l'appel).
  const forceRef = useRef(false);

  const fetcher = useCallback(
    (signal: AbortSignal) => {
      const force = forceRef.current;
      forceRef.current = false; // ne force que le fetch déclenché par forceRefresh
      return getReminders(today, force, signal);
    },
    [today],
  );
  const state = useAsync<CustomerDunningRow[]>(fetcher, [today]);
  const { refresh } = state;
  const [confirming, setConfirming] = useState(false);

  const forceRefresh = useCallback(() => {
    forceRef.current = true;
    refresh();
  }, [refresh]);

  const fetchDraft = useCallback(
    (customerId: number) => apiGetDraft(customerId, today),
    [today],
  );

  const confirmSent = useCallback(
    async (customerId: number, body: ConfirmSentIn) => {
      setConfirming(true);
      try {
        const entry = await apiConfirmSent(customerId, body);
        refresh(); // la relance loggée peut changer suggested_level
        return entry;
      } finally {
        setConfirming(false);
      }
    },
    [refresh],
  );

  return { ...state, fetchDraft, confirmSent, confirming, forceRefresh };
}
