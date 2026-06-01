// Helpers de formatage (montants, dates). Coerce les Decimal sérialisés
// (nombre ou chaîne) avant affichage.

import type { Money } from "./api-client/types";

export function toNumber(v: Money | null | undefined): number {
  if (v == null) return 0;
  const n = typeof v === "number" ? v : parseFloat(v);
  return Number.isFinite(n) ? n : 0;
}

const eurFmt = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

const eurFmt2 = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Montant arrondi à l'euro (KPIs, totaux de liste). */
export const eur = (v: Money | null | undefined): string => eurFmt.format(toNumber(v));

/** Montant au centime (factures, matchs). */
export const eur2 = (v: Money | null | undefined): string => eurFmt2.format(toNumber(v));

export function days(v: Money | null | undefined): string {
  const n = Math.round(toNumber(v));
  return `${n} j`;
}

const dateFmt = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const dateTimeFmt = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : dateFmt.format(d);
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : dateTimeFmt.format(d);
}

/** Nombre de jours de retard depuis une échéance (négatif si non échu). */
export function daysOverdue(dueIso: string | null | undefined, today = new Date()): number | null {
  if (!dueIso) return null;
  const d = new Date(dueIso);
  if (Number.isNaN(d.getTime())) return null;
  return Math.floor((today.getTime() - d.getTime()) / 86_400_000);
}
