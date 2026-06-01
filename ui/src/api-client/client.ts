// Client REST typé de l'API Relance EHS.
//
// base = import.meta.env.VITE_API_BASE (injecté au build en prod). En dev il
// reste vide : les requêtes partent en relatif sur /api, proxifiées vers
// http://localhost:8000 par Vite (cf. vite.config.ts).

import type {
  ConfirmSentBody,
  CustomerDunningRow,
  Draft,
  Invoice,
  PaymentMatch,
  ReminderLogEntry,
  Stats,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { Accept: "application/json", ...(init?.headers ?? {}) },
      ...init,
    });
  } catch {
    throw new ApiError(0, "API injoignable — l'API tourne-t-elle sur :8000 ?");
  }

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* corps non-JSON : on garde le statut */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function withToday(path: string, today?: string): string {
  return today ? `${path}${path.includes("?") ? "&" : "?"}today=${today}` : path;
}

export const api = {
  // ----- Stats / dashboard -----
  getStats: (today?: string) => request<Stats>(withToday("/api/stats", today)),

  // ----- Grand livre (aging brut) -----
  getLedger: (today?: string) =>
    request<CustomerDunningRow[]>(withToday("/api/ledger", today)),

  getCustomerInvoices: (customerId: number) =>
    request<Invoice[]>(`/api/ledger/${customerId}`),

  // ----- Relances (vue enrichie banque + historique) -----
  getReminders: (today?: string) =>
    request<CustomerDunningRow[]>(withToday("/api/reminders", today)),

  getHistory: (customerId?: number, limit = 100) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (customerId != null) q.set("customer_id", String(customerId));
    return request<ReminderLogEntry[]>(`/api/reminders/history?${q.toString()}`);
  },

  getDraft: (customerId: number, today?: string) =>
    request<Draft>(withToday(`/api/reminders/${customerId}/draft`, today)),

  confirmSent: (customerId: number, body: ConfirmSentBody) =>
    request<ReminderLogEntry>(`/api/reminders/${customerId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  // ----- Banque (rapprochement HSBC) -----
  uploadBank: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<PaymentMatch[]>("/api/bank/upload", {
      method: "POST",
      body: form,
    });
  },

  getMatches: (since?: string) =>
    request<PaymentMatch[]>(since ? `/api/bank/matches?since=${since}` : "/api/bank/matches"),
};
