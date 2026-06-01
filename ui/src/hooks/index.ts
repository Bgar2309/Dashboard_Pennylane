// Hooks de données (fetch + état) et store de toasts. Sans dépendance externe :
// useState/useEffect pour les requêtes, useSyncExternalStore pour les toasts.

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { api, ApiError } from "../api-client/client";
import type {
  CustomerDunningRow,
  Draft,
  Invoice,
  PaymentMatch,
  ReminderLogEntry,
  Stats,
} from "../api-client/types";

// --------------------------------------------------------------------------
// useAsync — exécute un loader, expose { data, loading, error, reload }
// --------------------------------------------------------------------------

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useAsync<T>(
  loader: () => Promise<T>,
  deps: ReadonlyArray<unknown> = []
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    loaderRef.current()
      .then((d) => alive && setData(d))
      .catch((e: unknown) => {
        if (!alive) return;
        setError(e instanceof ApiError ? e.message : String(e));
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, loading, error, reload };
}

// --------------------------------------------------------------------------
// Hooks métier
// --------------------------------------------------------------------------

export const useStats = (today?: string) =>
  useAsync<Stats>(() => api.getStats(today), [today]);

/** Vue « relances à faire » : aging enrichi banque + historique. */
export const useReminders = (today?: string) =>
  useAsync<CustomerDunningRow[]>(() => api.getReminders(today), [today]);

/** Grand livre brut (aging seul). */
export const useLedger = (today?: string) =>
  useAsync<CustomerDunningRow[]>(() => api.getLedger(today), [today]);

export const useCustomerInvoices = (customerId: number | null) =>
  useAsync<Invoice[]>(
    () => (customerId == null ? Promise.resolve([]) : api.getCustomerInvoices(customerId)),
    [customerId]
  );

export const useDraft = (customerId: number | null, today?: string) =>
  useAsync<Draft>(
    () =>
      customerId == null
        ? Promise.resolve({ customer_id: -1, draft: "" })
        : api.getDraft(customerId, today),
    [customerId, today]
  );

export const useHistory = (customerId?: number, limit = 100) =>
  useAsync<ReminderLogEntry[]>(() => api.getHistory(customerId, limit), [customerId, limit]);

/** Upload d'un relevé bancaire HSBC → matchs. */
export function useBankUpload() {
  const [matches, setMatches] = useState<PaymentMatch[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFile, setLastFile] = useState<string | null>(null);

  const upload = useCallback(async (file: File): Promise<PaymentMatch[] | null> => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.uploadBank(file);
      setMatches(res);
      setLastFile(file.name);
      return res;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { matches, loading, error, lastFile, upload };
}

// --------------------------------------------------------------------------
// Toasts — store module-level partagé + hook d'abonnement
// --------------------------------------------------------------------------

export type ToastKind = "success" | "error" | "info";
export interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
}

let toasts: Toast[] = [];
const listeners = new Set<() => void>();
let seq = 0;

function emit() {
  listeners.forEach((l) => l());
}

export function pushToast(message: string, kind: ToastKind = "info", ttl = 4000) {
  const id = ++seq;
  toasts = [...toasts, { id, message, kind }];
  emit();
  if (ttl > 0) setTimeout(() => dismissToast(id), ttl);
}

export function dismissToast(id: number) {
  toasts = toasts.filter((t) => t.id !== id);
  emit();
}

export function useToasts(): Toast[] {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => toasts,
    () => toasts
  );
}
