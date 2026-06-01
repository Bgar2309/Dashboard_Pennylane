// Liste des factures ouvertes d'un client (reste dû, retard).

import type { Invoice } from "../api-client/types";
import { daysOverdue, eur2, fmtDate } from "../format";

export function InvoiceList({ invoices }: { invoices: Invoice[] }) {
  if (invoices.length === 0) {
    return <div className="muted">Aucune facture ouverte.</div>;
  }

  const total = invoices.reduce(
    (s, inv) => s + (typeof inv.remaining_amount === "number" ? inv.remaining_amount : parseFloat(inv.remaining_amount) || 0),
    0
  );

  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>N° facture</th>
            <th>Échéance</th>
            <th>Retard</th>
            <th className="num">Reste dû</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((inv) => {
            const od = daysOverdue(inv.due_date);
            return (
              <tr key={inv.id}>
                <td className="mono" style={{ fontWeight: 600 }}>{inv.number}</td>
                <td className="mono muted">{fmtDate(inv.due_date)}</td>
                <td className="mono">
                  {od == null ? (
                    <span className="muted">—</span>
                  ) : od > 0 ? (
                    <span style={{ color: "var(--vermillion-d)", fontWeight: 600 }}>+{od} j</span>
                  ) : (
                    <span className="muted">à échoir</span>
                  )}
                </td>
                <td className="num mono" style={{ fontWeight: 600 }}>{eur2(inv.remaining_amount)}</td>
              </tr>
            );
          })}
          <tr>
            <td colSpan={3} style={{ fontWeight: 600, borderTop: "1.5px solid var(--ink)" }}>
              Total reste dû
            </td>
            <td
              className="num mono"
              style={{ fontWeight: 700, borderTop: "1.5px solid var(--ink)" }}
            >
              {eur2(total)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
