// useReminders — vue relances à faire (GET /api/reminders) + actions
// brouillon / confirmation d'envoi.

import { useCallback, useState } from "react";

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
}

/** Vue relances : aging + blocage paiement + anti-spam, avec actions. */
export function useReminders(today?: IsoDate): UseRemindersResult {
  const fetcher = useCallback(
    (signal: AbortSignal) => getReminders(today, signal),
    [today],
  );
  const state = useAsync<CustomerDunningRow[]>(fetcher, [today]);
  const { refresh } = state;
  const [confirming, setConfirming] = useState(false);

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

  return { ...state, fetchDraft, confirmSent, confirming };
}
