// Types miroir des schemas API (cf. backend/api/schemas.py).
// Les montants Decimal côté Pydantic peuvent arriver en nombre OU en chaîne
// selon la sérialisation : on tolère les deux via `Money` et on coerce au format.

export type ReminderLevel = "none" | "first" | "second" | "formal";
export type AgingBucket = "not_due" | "0-30" | "30-60" | "60-90" | "90+";
export type MatchConfidence = "strong" | "medium" | "weak" | "none";

export type Money = number | string;

export interface Customer {
  id: number;
  name: string;
  email: string | null;
}

export interface Invoice {
  id: number;
  number: string;
  customer_id: number;
  customer_name: string;
  date: string;
  due_date: string | null;
  amount: Money;
  currency: string;
  paid: boolean;
  remaining_amount: Money;
}

export interface ReminderLogEntry {
  id: number;
  customer_id: number;
  customer_name: string;
  level: ReminderLevel;
  sent_at: string;
  invoice_numbers: string[];
  note: string | null;
}

export interface CustomerDunningRow {
  customer: Customer;
  open_invoices: Invoice[];
  total_due: Money;
  oldest_due_date: string | null;
  worst_bucket: AgingBucket;
  suggested_level: ReminderLevel;
  last_reminder: ReminderLogEntry | null;
  blocked_by_payment: boolean;
}

export interface PaymentMatch {
  bank_ref: string;
  invoice_id: number | null;
  invoice_number: string | null;
  customer_name: string | null;
  amount: Money;
  confidence: MatchConfidence;
  matched_invoice_numbers: string[];
  reason: string;
}

export interface Draft {
  customer_id: number;
  draft: string;
}

export interface TopOverdueItem {
  customer_id: number;
  customer_name: string;
  total_due: Money;
  worst_bucket: string;
  oldest_due_date: string | null;
  suggested_level: string;
  open_invoices_count: number;
}

export interface Stats {
  encours_total: Money;
  clients_a_relancer: number;
  dso_approche: Money;
  retard_moyen_pondere: Money;
  total_par_bucket: Record<string, Money>;
  top_overdue: TopOverdueItem[];
}

export interface ConfirmSentBody {
  level: ReminderLevel;
  invoice_numbers: string[];
  note?: string | null;
}

export const AGING_ORDER: AgingBucket[] = [
  "not_due",
  "0-30",
  "30-60",
  "60-90",
  "90+",
];

export const BUCKET_LABEL: Record<AgingBucket, string> = {
  not_due: "Non échu",
  "0-30": "0 – 30 j",
  "30-60": "30 – 60 j",
  "60-90": "60 – 90 j",
  "90+": "+ de 90 j",
};

export const LEVEL_LABEL: Record<ReminderLevel, string> = {
  none: "Aucune",
  first: "1ʳᵉ relance",
  second: "2ᵉ relance",
  formal: "Mise en demeure",
};

export const CONFIDENCE_LABEL: Record<MatchConfidence, string> = {
  strong: "Forte",
  medium: "Moyenne",
  weak: "Faible",
  none: "Aucune",
};
