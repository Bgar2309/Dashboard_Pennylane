// Pastilles sémantiques : niveau de relance, bucket d'âge, confiance de match,
// et le badge « Payé (banque) ».

import {
  BUCKET_LABEL,
  CONFIDENCE_LABEL,
  LEVEL_LABEL,
  type AgingBucket,
  type MatchConfidence,
  type ReminderLevel,
} from "../api-client/types";

export function ReminderLevelTag({ level }: { level: ReminderLevel }) {
  return (
    <span className={`tag lvl-${level}`}>
      <span className="dot" />
      {LEVEL_LABEL[level]}
    </span>
  );
}

export function BucketTag({ bucket }: { bucket: AgingBucket }) {
  // classe CSS : "90+" -> "bk-90"
  const cls = bucket === "90+" ? "bk-90" : `bk-${bucket}`;
  return <span className={`tag bk ${cls}`}>{BUCKET_LABEL[bucket]}</span>;
}

export function ConfidenceTag({ confidence }: { confidence: MatchConfidence }) {
  return <span className={`tag cf-${confidence}`}>{CONFIDENCE_LABEL[confidence]}</span>;
}

export function PaymentBadge({ label = "Payé (banque)" }: { label?: string }) {
  return (
    <span className="pay-badge">
      <span aria-hidden>◆</span>
      {label}
    </span>
  );
}
