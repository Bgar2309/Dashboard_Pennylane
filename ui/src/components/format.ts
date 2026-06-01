// Helpers d'affichage purs (aucun I/O). Les montants arrivent en chaînes
// (Decimal sérialisé) : on parse au plus tard, uniquement pour formater.

import type {
  AgingBucket,
  Decimal,
  IsoDate,
  IsoDateTime,
  MatchConfidence,
  ReminderLevel,
} from "../api-client";

const EUR = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 2,
});

const EUR_COMPACT = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  notation: "compact",
  maximumFractionDigits: 1,
});

const DATE_FMT = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const DATETIME_FMT = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** Montant TTC formaté en euros (devise par défaut EUR). */
export function money(value: Decimal | number, currency = "EUR"): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "—";
  if (currency === "EUR") return EUR.format(n);
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(n);
}

/** Montant en notation compacte (« 12,4 k € ») pour les KPIs serrés. */
export function moneyCompact(value: Decimal | number): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "—";
  return EUR_COMPACT.format(n);
}

/** Nombre de jours formaté (« 37 j »), ou tiret si non fini. */
export function days(value: Decimal | number): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "—";
  return `${Math.round(n)} j`;
}

export function date(value: IsoDate | null | undefined): string {
  if (!value) return "—";
  const d = new Date(`${value}T00:00:00`);
  return Number.isNaN(d.getTime()) ? "—" : DATE_FMT.format(d);
}

export function dateTime(value: IsoDateTime | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : DATETIME_FMT.format(d);
}

/** Jours de retard depuis une échéance, relativement à `today` (négatif = à échoir). */
export function daysOverdue(due: IsoDate | null, today: IsoDate): number | null {
  if (!due) return null;
  const d = new Date(`${due}T00:00:00`).getTime();
  const t = new Date(`${today}T00:00:00`).getTime();
  if (Number.isNaN(d) || Number.isNaN(t)) return null;
  return Math.round((t - d) / 86_400_000);
}

// --- Libellés métier (FR) ---

export const BUCKET_ORDER: AgingBucket[] = [
  "not_due",
  "0-30",
  "30-60",
  "60-90",
  "90+",
];

export const BUCKET_LABEL: Record<string, string> = {
  not_due: "À échoir",
  "0-30": "0 – 30 j",
  "30-60": "30 – 60 j",
  "60-90": "60 – 90 j",
  "90+": "90 j et +",
};

export const BUCKET_VAR: Record<string, string> = {
  not_due: "var(--age-notdue)",
  "0-30": "var(--age-0)",
  "30-60": "var(--age-30)",
  "60-90": "var(--age-60)",
  "90+": "var(--age-90)",
};

export const LEVEL_LABEL: Record<ReminderLevel, string> = {
  none: "Aucune",
  first: "1re relance",
  second: "2e relance",
  formal: "Mise en demeure",
};

export const CONF_LABEL: Record<MatchConfidence, string> = {
  strong: "Forte",
  medium: "Moyenne",
  weak: "Faible",
  none: "Aucune",
};
