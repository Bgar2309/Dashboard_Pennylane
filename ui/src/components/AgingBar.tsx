// Barre d'âge empilée : répartition de l'encours par bucket + légende.

import { AGING_ORDER, BUCKET_LABEL, type AgingBucket, type Money } from "../api-client/types";
import { eur, toNumber } from "../format";

const BUCKET_COLOR: Record<AgingBucket, string> = {
  not_due: "var(--age-not_due)",
  "0-30": "var(--age-0-30)",
  "30-60": "var(--age-30-60)",
  "60-90": "var(--age-60-90)",
  "90+": "var(--age-90)",
};

export function AgingBar({ buckets }: { buckets: Record<string, Money> }) {
  const entries = AGING_ORDER.map((b) => ({
    bucket: b,
    amount: toNumber(buckets[b]),
  }));
  const total = entries.reduce((s, e) => s + e.amount, 0);

  if (total <= 0) {
    return <div className="muted">Aucun encours à répartir.</div>;
  }

  return (
    <div>
      <div className="aging-bar">
        {entries.map((e) =>
          e.amount > 0 ? (
            <div
              key={e.bucket}
              className="aging-seg"
              style={{ width: `${(e.amount / total) * 100}%`, background: BUCKET_COLOR[e.bucket] }}
              title={`${BUCKET_LABEL[e.bucket]} — ${eur(e.amount)}`}
            />
          ) : null
        )}
      </div>
      <div className="aging-legend">
        {entries.map((e) => (
          <div key={e.bucket} className="aging-leg-item">
            <span className="aging-dot" style={{ background: BUCKET_COLOR[e.bucket] }} />
            <span className="leg-name">{BUCKET_LABEL[e.bucket]}</span>
            <span className="leg-val mono">{eur(e.amount)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
