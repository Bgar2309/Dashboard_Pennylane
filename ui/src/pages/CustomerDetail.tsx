// Détail d'un client sélectionné : factures ouvertes + brouillon de relance.

import { Card, DraftPanel, Icon, InvoiceList } from "../components";
import { BucketTag, PaymentBadge } from "../components/Tags";
import type { CustomerDunningRow } from "../api-client/types";
import { eur, fmtDate, fmtDateTime } from "../format";
import { LEVEL_LABEL } from "../api-client/types";

export function CustomerDetail({
  row,
  today,
  onBack,
  onConfirmed,
}: {
  row: CustomerDunningRow;
  today?: string;
  onBack: () => void;
  onConfirmed?: () => void;
}) {
  return (
    <div className="reveal stack">
      <button className="btn btn-ghost" style={{ alignSelf: "flex-start" }} onClick={onBack}>
        <Icon name="arrowLeft" size={16} />
        Retour au grand livre
      </button>

      <div className="row-between" style={{ alignItems: "flex-start" }}>
        <div>
          <h2 style={{ fontSize: 28 }}>{row.customer.name}</h2>
          <div className="muted" style={{ marginTop: 4 }}>
            {row.customer.email ?? "Email inconnu"}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 12, alignItems: "center" }}>
            <BucketTag bucket={row.worst_bucket} />
            {row.blocked_by_payment && <PaymentBadge />}
            {row.last_reminder && (
              <span className="muted" style={{ fontSize: 12 }}>
                Dernière relance ({LEVEL_LABEL[row.last_reminder.level]}) ·{" "}
                {fmtDateTime(row.last_reminder.sent_at)}
              </span>
            )}
          </div>
        </div>
        <div className="head-meta">
          <span className="big mono">{eur(row.total_due)}</span>
          encours dû · échéance {fmtDate(row.oldest_due_date)}
        </div>
      </div>

      <div className="grid-detail">
        <Card title="Factures ouvertes">
          <InvoiceList invoices={row.open_invoices} />
        </Card>

        <DraftPanel row={row} today={today} onConfirmed={onConfirmed} />
      </div>
    </div>
  );
}
