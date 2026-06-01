// Types miroir des schemas API (core dataclasses). TODO: compléter.
export type ReminderLevel = "none" | "first" | "second" | "formal";
export type AgingBucket = "not_due" | "0-30" | "30-60" | "60-90" | "90+";
export type MatchConfidence = "strong" | "medium" | "weak" | "none";
// TODO: Invoice, Customer, CustomerDunningRow, PaymentMatch, ReminderLogEntry, Stats
