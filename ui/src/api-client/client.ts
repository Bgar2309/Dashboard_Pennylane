/// <reference types="vite/client" />
// Client REST typé. Une fonction par endpoint de l'API (cf. ARCHITECTURE.md).
// Base = import.meta.env.VITE_API_BASE. Aucune logique métier : on appelle,
// on (dé)sérialise, on remonte les erreurs typées.

import type {
  ConfirmSentIn,
  CustomerDunningRow,
  Draft,
  Invoice,
  IsoDate,
  PaymentMatch,
  ReminderLogEntry,
  Stats,
} from "./types";

/** Base de l'API, sans slash final. */
const API_BASE: string = String(
  import.meta.env.VITE_API_BASE ?? "",
).replace(/\/+$/, "");

/** Erreur HTTP enrichie (status + corps `detail` FastAPI si présent). */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Construit une URL absolue avec query params (les `undefined`/`null` sont ignorés). */
function buildUrl(
  path: string,
  params?: Record<string, string | number | undefined | null>,
): string {
  const url = `${API_BASE}${path}`;
  if (!params) return url;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      search.append(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `${url}?${qs}` : url;
}

/** Extrait le `detail` d'une réponse d'erreur FastAPI sans planter. */
async function readError(res: Response): Promise<ApiError> {
  let detail: unknown = null;
  let message = `${res.status} ${res.statusText}`;
  try {
    const body = await res.json();
    detail = (body as { detail?: unknown })?.detail ?? body;
    if (typeof detail === "string") message = detail;
  } catch {
    // corps non-JSON ou vide : on garde le message par défaut
  }
  return new ApiError(res.status, detail, message);
}

/** Exécute une requête et parse le JSON, en lançant `ApiError` sur échec. */
async function request<T>(
  path: string,
  init?: RequestInit,
  params?: Record<string, string | number | undefined | null>,
): Promise<T> {
  const res = await fetch(buildUrl(path, params), init);
  if (!res.ok) throw await readError(res);
  return (await res.json()) as T;
}

// --- ledger ---

/** GET /api/ledger → grand livre client agrégé. */
export function getLedger(
  today?: IsoDate,
  signal?: AbortSignal,
): Promise<CustomerDunningRow[]> {
  return request<CustomerDunningRow[]>("/api/ledger", { signal }, { today });
}

/** GET /api/ledger/{customer_id} → factures ouvertes d'un client. */
export function getCustomerInvoices(
  customerId: number,
  signal?: AbortSignal,
): Promise<Invoice[]> {
  return request<Invoice[]>(`/api/ledger/${customerId}`, { signal });
}

// --- reminders ---

/** GET /api/reminders → vue relances à faire (blocage banque + anti-spam). */
export function getReminders(
  today?: IsoDate,
  signal?: AbortSignal,
): Promise<CustomerDunningRow[]> {
  return request<CustomerDunningRow[]>("/api/reminders", { signal }, { today });
}

/** GET /api/reminders/{cid}/draft → texte du brouillon (ne logue rien). */
export function getDraft(
  customerId: number,
  today?: IsoDate,
  signal?: AbortSignal,
): Promise<Draft> {
  return request<Draft>(
    `/api/reminders/${customerId}/draft`,
    { signal },
    { today },
  );
}

/** POST /api/reminders/{cid}/confirm → log d'envoi (seul point d'écriture). */
export function confirmSent(
  customerId: number,
  body: ConfirmSentIn,
  signal?: AbortSignal,
): Promise<ReminderLogEntry> {
  return request<ReminderLogEntry>(`/api/reminders/${customerId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}

/** GET /api/reminders/history → historique des relances loggées. */
export function getHistory(
  options?: { customerId?: number; limit?: number },
  signal?: AbortSignal,
): Promise<ReminderLogEntry[]> {
  return request<ReminderLogEntry[]>(
    "/api/reminders/history",
    { signal },
    { customer_id: options?.customerId, limit: options?.limit },
  );
}

// --- bank ---

/** POST /api/bank/upload (multipart) → parse + match + persiste les matchs. */
export function uploadBank(
  file: File,
  signal?: AbortSignal,
): Promise<PaymentMatch[]> {
  const form = new FormData();
  form.append("file", file);
  return request<PaymentMatch[]>("/api/bank/upload", {
    method: "POST",
    body: form, // pas de Content-Type manuel : le navigateur fixe le boundary
    signal,
  });
}

/** GET /api/bank/matches → derniers matchs calculés. */
export function getMatches(
  since?: IsoDate,
  signal?: AbortSignal,
): Promise<PaymentMatch[]> {
  return request<PaymentMatch[]>("/api/bank/matches", { signal }, { since });
}

// --- stats ---

/** GET /api/stats → KPIs dashboard. */
export function getStats(today?: IsoDate, signal?: AbortSignal): Promise<Stats> {
  return request<Stats>("/api/stats", { signal }, { today });
}
