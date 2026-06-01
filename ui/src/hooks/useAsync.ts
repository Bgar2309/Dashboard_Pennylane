// Petit socle partagé pour les hooks de lecture : exécute une promesse,
// expose { data, loading, error, refresh }, annule la requête en vol au
// démontage / re-fetch, et ignore les réponses obsolètes (race conditions).

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api-client";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | Error | null;
  /** Relance la requête manuellement (ex : après une mutation). */
  refresh: () => void;
}

/**
 * Lance `fetcher(signal)` au montage puis à chaque changement de `deps`.
 * `fetcher` doit être stable (le mémoïser chez l'appelant si besoin).
 */
export function useAsync<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[],
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [tick, setTick] = useState(0);

  // Garde la dernière requête lancée pour ignorer les réponses périmées.
  const runIdRef = useRef(0);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    const runId = ++runIdRef.current;
    setLoading(true);
    setError(null);

    fetcher(controller.signal)
      .then((result) => {
        if (runId === runIdRef.current) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || runId !== runIdRef.current) return;
        setError(err instanceof Error ? err : new Error(String(err)));
        setLoading(false);
      });

    return () => controller.abort();
    // `fetcher` et `deps` pilotent le re-fetch ; `tick` force un refresh manuel.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher, tick, ...deps]);

  return { data, loading, error, refresh };
}
