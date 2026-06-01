// Liste des factures ouvertes d'un client : n°, dates, montant TTC, reste dû
// et retard en jours par rapport à la date courante.

import type { Invoice, IsoDate } from "../api-client";
import { date, daysOverdue, money } from "./format";

function OverdueCell({ due, today }: { due: IsoDate | null; today: IsoDate }) {
  const d = daysOverdue(due, today);
  if (d === null) return <span className="cust__meta">—</span>;
  if (d <= 0) return <span className="cust__meta">à échoir</span>;
  return (
    <span className="num" style={{ color: "var(--accent)", fontWeight: 600 }}>
      +{d} j
    </span>
  );
}

export function InvoiceList({
  invoices,
  today,
}: {
  invoices: Invoice[];
  today: IsoDate;
}) {
  if (invoices.length === 0) {
    return <div className="empty">Aucune facture ouverte.</div>;
  }

  return (
    <table className="tbl">
      <thead>
        <tr>
          <th>Facture</th>
          <th>Échéance</th>
          <th>Retard</th>
          <th className="r">Reste dû</th>
        </tr>
      </thead>
      <tbody>
        {invoices.map((inv) => (
          <tr key={inv.id}>
            <td>
              <div className="cust">
                <span className="cust__name num">{inv.number}</span>
                <span className="cust__meta">émise le {date(inv.date)}</span>
              </div>
            </td>
            <td className="num">{date(inv.due_date)}</td>
            <td>
              <OverdueCell due={inv.due_date} today={today} />
            </td>
            <td className="r tbl__amount">
              {money(inv.remaining_amount, inv.currency)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
