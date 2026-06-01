// Barre d'âge empilée : répartition de l'encours par tranche d'ancienneté,
// avec légende chiffrée. Les segments sont proportionnels au montant.

import type { Decimal } from "../api-client";
import { BUCKET_LABEL, BUCKET_ORDER, BUCKET_VAR, money } from "./format";

export function AgingBar({
  totals,
}: {
  totals: Record<string, Decimal>;
}) {
  const entries = BUCKET_ORDER.map((bucket) => ({
    bucket,
    amount: Number(totals[bucket] ?? 0),
  }));
  const total = entries.reduce((s, e) => s + (e.amount > 0 ? e.amount : 0), 0);

  if (total <= 0) {
    return <div className="empty">Aucun encours à répartir.</div>;
  }

  return (
    <div className="aging">
      <div className="aging__bar" role="img" aria-label="Répartition de l'encours par âge">
        {entries.map((e) =>
          e.amount > 0 ? (
            <div
              key={e.bucket}
              className="aging__seg"
              style={{
                width: `${(e.amount / total) * 100}%`,
                background: BUCKET_VAR[e.bucket],
              }}
              title={`${BUCKET_LABEL[e.bucket]} · ${money(e.amount)}`}
            />
          ) : null,
        )}
      </div>
      <div className="aging__legend">
        {entries.map((e) => (
          <div className="aging__row" key={e.bucket}>
            <span
              className="aging__swatch"
              style={{ background: BUCKET_VAR[e.bucket] }}
            />
            <span className="aging__rk">{BUCKET_LABEL[e.bucket]}</span>
            <span className="aging__rv">{money(e.amount)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
