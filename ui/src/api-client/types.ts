// Types miroir des schemas API (`backend/api/schemas.py`, eux-mêmes miroir des
// dataclasses `core`). Les montants (`Decimal` côté Python) sont sérialisés en
// JSON comme des chaînes : on les garde en `string` pour ne perdre aucune
// précision, le formatage est fait à l'affichage.

// --- Enums (str enums côté Python) ---
export type ReminderLevel = "none" | "first" | "second" | "formal";
export type AgingBucket = "not_due" | "0-30" | "30-60" | "60-90" | "90+";
export type MatchConfidence = "strong" | "medium" | "weak" | "none";

/** Montant TTC sérialisé : `Decimal` Python → chaîne JSON (précision préservée). */
export type Decimal = string;
/** Date ISO `YYYY-MM-DD`. */
export type IsoDate = string;
/** Datetime ISO 8601. */
export type IsoDateTime = string;

// --- Schémas de sortie (miroir des *Out) ---

/** `CustomerOut` — client Pennylane (identité minimale). */
export interface Customer {
  id: number;
  name: string;
  email: string | null;
}

/** `InvoiceOut` — facture client (TTC + reste dû). */
export interface Invoice {
  id: number;
  number: string;
  customer_id: number;
  customer_name: string;
  date: IsoDate;
  due_date: IsoDate | null;
  amount: Decimal;
  currency: string;
  paid: boolean;
  remaining_amount: Decimal;
}

/** `ReminderLogEntryOut` — une relance loggée comme envoyée. */
export interface ReminderLogEntry {
  id: number;
  customer_id: number;
  customer_name: string;
  level: ReminderLevel;
  sent_at: IsoDateTime;
  invoice_numbers: string[];
  note: string | null;
}

/** `CustomerDunningRowOut` — ligne du grand livre client agrégée pour la relance. */
export interface CustomerDunningRow {
  customer: Customer;
  open_invoices: Invoice[];
  total_due: Decimal;
  oldest_due_date: IsoDate | null;
  worst_bucket: AgingBucket;
  suggested_level: ReminderLevel;
  last_reminder: ReminderLogEntry | null;
  blocked_by_payment: boolean;
}

/** `PaymentMatchOut` — rapprochement transaction bancaire ↔ facture. */
export interface PaymentMatch {
  bank_ref: string;
  invoice_id: number | null;
  invoice_number: string | null;
  customer_name: string | null;
  amount: Decimal;
  confidence: MatchConfidence;
  matched_invoice_numbers: string[];
  reason: string;
}

/** `DraftOut` — texte d'un brouillon de relance (jamais loggé). */
export interface Draft {
  customer_id: number;
  draft: string;
}

/** `TopOverdueItem` — un client du top des retardataires. */
export interface TopOverdueItem {
  customer_id: number;
  customer_name: string;
  total_due: Decimal;
  worst_bucket: string;
  oldest_due_date: IsoDate | null;
  suggested_level: string;
  open_invoices_count: number;
}

/** `StatsOut` — KPIs du dashboard. */
export interface Stats {
  encours_total: Decimal;
  clients_a_relancer: number;
  dso_approche: Decimal;
  retard_moyen_pondere: Decimal;
  total_par_bucket: Record<string, Decimal>;
  top_overdue: TopOverdueItem[];
}

// --- Schémas d'entrée (miroir des *In) ---

/** `ConfirmSentIn` — corps du POST /reminders/{cid}/confirm. */
export interface ConfirmSentIn {
  level: ReminderLevel;
  invoice_numbers?: string[];
  note?: string | null;
}
