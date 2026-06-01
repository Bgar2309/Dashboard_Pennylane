// useBankUpload — upload d'un relevé HSBC (POST /api/bank/upload) et lecture
// des derniers matchs (GET /api/bank/matches). Hook de mutation : pas de
// fetch au montage, l'utilisateur déclenche `upload` ; `loadMatches` permet
// de récupérer les matchs déjà persistés.

import { useCallback, useState } from "react";

import {
  ApiError,
  getMatches,
  uploadBank,
  type IsoDate,
  type PaymentMatch,
} from "../api-client";

export interface UseBankUploadResult {
  /** Matchs courants (résultat du dernier upload ou de `loadMatches`). */
  matches: PaymentMatch[] | null;
  /** Vrai pendant un upload ou un chargement. */
  loading: boolean;
  error: ApiError | Error | null;
  /** Envoie un fichier HSBC (xlsx/pdf) → retourne et stocke les matchs. */
  upload: (file: File) => Promise<PaymentMatch[]>;
  /** Recharge les derniers matchs persistés (optionnellement depuis une date). */
  loadMatches: (since?: IsoDate) => Promise<PaymentMatch[]>;
  /** Réinitialise l'état (matchs + erreur). */
  reset: () => void;
}

function toError(err: unknown): ApiError | Error {
  return err instanceof Error ? err : new Error(String(err));
}

/** Gère l'upload de relevé bancaire et l'affichage des rapprochements. */
export function useBankUpload(): UseBankUploadResult {
  const [matches, setMatches] = useState<PaymentMatch[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const upload = useCallback(async (file: File) => {
    setLoading(true);
    setError(null);
    try {
      const result = await uploadBank(file);
      setMatches(result);
      return result;
    } catch (err) {
      setError(toError(err));
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMatches = useCallback(async (since?: IsoDate) => {
    setLoading(true);
    setError(null);
    try {
      const result = await getMatches(since);
      setMatches(result);
      return result;
    } catch (err) {
      setError(toError(err));
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setMatches(null);
    setError(null);
  }, []);

  return { matches, loading, error, upload, loadMatches, reset };
}
