// Grand livre client : une ligne par client, triée par encours décroissant.
// Les clients couverts par un paiement (blocked_by_payment) sont relégués en
// bas, marqués « Payé (banque) » et hors de la liste à relancer.

import type { CustomerDunningRow } from "../api-client";
import { PaymentBadge } from "./PaymentBadge";
import { ReminderLevelTag } from "./ReminderLevelTag";
import { BUCKET_LABEL, date, money } from "./format";

function sortRows(rows: CustomerDunningRow[]): CustomerDunningRow[] {
  return [...rows].sort((a, b) => {
    if (a.blocked_by_payment !== b.blocked_by_payment) {
      return a.blocked_by_payment ? 1 : -1;
    }
    return Number(b.total_due) - Number(a.total_due);
  });
}

export function CustomerTable({
  rows,
  selectedId,
  onSelect,
}: {
  rows: CustomerDunningRow[];
  selectedId: number | null;
  onSelect: (row: CustomerDunningRow) => void;
}) {
  if (rows.length === 0) {
    return <div className="empty">Aucun client à afficher pour cette date.</div>;
  }

  return (
    <table className="tbl tbl--rows">
      <thead>
        <tr>
          <th>Client</th>
          <th>Âge</th>
          <th>Échéance la + ancienne</th>
          <th>Relance</th>
          <th className="r">Encours dû</th>
        </tr>
      </thead>
      <tbody>
        {sortRows(rows).map((row) => {
          const id = row.customer.id;
          const blocked = row.blocked_by_payment;
          return (
            <tr
              key={id}
              onClick={() => onSelect(row)}
              className={[
                id === selectedId ? "is-selected" : "",
                blocked ? "is-blocked" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <td>
                <div className="cust">
                  <span className="cust__name">{row.customer.name}</span>
                  <span className="cust__meta">
                    {row.open_invoices.length} facture
                    {row.open_invoices.length > 1 ? "s" : ""} ouverte
                    {row.open_invoices.length > 1 ? "s" : ""}
                    {row.customer.email ? ` · ${row.customer.email}` : ""}
                  </span>
                </div>
              </td>
              <td>
                <span className={`bk bk-${row.worst_bucket}`}>
                  {BUCKET_LABEL[row.worst_bucket]}
                </span>
              </td>
              <td className="num">{date(row.oldest_due_date)}</td>
              <td>
                {blocked ? (
                  <PaymentBadge />
                ) : (
                  <ReminderLevelTag level={row.suggested_level} />
                )}
              </td>
              <td className="r tbl__amount">{money(row.total_due)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
