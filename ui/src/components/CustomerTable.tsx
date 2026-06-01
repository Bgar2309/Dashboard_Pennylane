// Table du grand livre client : une ligne par client (CustomerDunningRow).
// Sélection cliquable. Affiche le PaymentBadge pour les clients bloqués banque.

import type { CustomerDunningRow } from "../api-client/types";
import { eur, fmtDate } from "../format";
import { BucketTag, PaymentBadge, ReminderLevelTag } from "./Tags";

export function CustomerTable({
  rows,
  selectedId,
  onSelect,
}: {
  rows: CustomerDunningRow[];
  selectedId?: number | null;
  onSelect?: (row: CustomerDunningRow) => void;
}) {
  return (
    <div className="tbl-wrap">
      <table className={`tbl ${onSelect ? "rows-clickable" : ""}`}>
        <thead>
          <tr>
            <th>Client</th>
            <th>Âge max</th>
            <th>Plus ancienne échéance</th>
            <th>Action suggérée</th>
            <th className="num">Encours dû</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const selected = selectedId === row.customer.id;
            return (
              <tr
                key={row.customer.id}
                className={selected ? "selected" : ""}
                onClick={onSelect ? () => onSelect(row) : undefined}
              >
                <td>
                  <div className="cust-name">{row.customer.name}</div>
                  <div className="cust-sub">
                    {row.open_invoices.length} facture{row.open_invoices.length > 1 ? "s" : ""}{" "}
                    ouverte{row.open_invoices.length > 1 ? "s" : ""}
                    {row.customer.email ? ` · ${row.customer.email}` : ""}
                  </div>
                </td>
                <td><BucketTag bucket={row.worst_bucket} /></td>
                <td className="mono muted">{fmtDate(row.oldest_due_date)}</td>
                <td>
                  {row.blocked_by_payment ? (
                    <PaymentBadge />
                  ) : (
                    <ReminderLevelTag level={row.suggested_level} />
                  )}
                </td>
                <td className="num mono" style={{ fontWeight: 600 }}>{eur(row.total_due)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
