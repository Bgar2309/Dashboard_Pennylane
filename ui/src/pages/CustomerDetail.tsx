// Panneau détail d'un client sélectionné : en-tête + factures ouvertes
// (InvoiceList) + brouillon de relance (DraftPanel). Le brouillon est lu via
// getDraft (rien n'est consigné), l'envoi confirmé via confirmSent.
//
// Un bouton « Voir le relevé » charge à la demande l'historique débit/crédit du
// client (getCustomerStatement) et l'affiche dans un tableau repliable.

import { useState } from "react";

import type {
  ConfirmSentIn,
  CustomerDunningRow,
  CustomerStatement,
  Draft,
  IsoDate,
  ReminderLogEntry,
} from "../api-client";
import { getCustomerStatement } from "../api-client";
import {
  DraftPanel,
  InvoiceList,
  PaymentBadge,
  ReminderLevelTag,
  date,
  dateTime,
  money,
} from "../components";

function StatementTable({ statement }: { statement: CustomerStatement }) {
  if (statement.entries.length === 0) {
    return <div className="empty">Aucune écriture pour ce client.</div>;
  }
  return (
    <table className="tbl">
      <thead>
        <tr>
          <th>Date</th>
          <th>Type</th>
          <th>Libellé</th>
          <th className="r">Débit</th>
          <th className="r">Crédit</th>
          <th className="r">Solde</th>
        </tr>
      </thead>
      <tbody>
        {statement.entries.map((e, i) => (
          <tr key={`${e.type}-${e.number ?? ""}-${i}`}>
            <td className="num">{date(e.date)}</td>
            <td>{e.type}</td>
            <td>{e.label}</td>
            <td className="r tbl__amount">{e.debit ? money(e.debit) : "—"}</td>
            <td className="r tbl__amount">{e.credit ? money(e.credit) : "—"}</td>
            <td className="r tbl__amount">{money(e.balance)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function CustomerDetail({
  row,
  today,
  fetchDraft,
  confirmSent,
  confirming,
  onConfirmed,
}: {
  row: CustomerDunningRow;
  today: IsoDate;
  fetchDraft: (customerId: number) => Promise<Draft>;
  confirmSent: (customerId: number, body: ConfirmSentIn) => Promise<ReminderLogEntry>;
  confirming: boolean;
  onConfirmed?: (entry: ReminderLogEntry) => void;
}) {
  const last = row.last_reminder;
  const customerId = row.customer.id;

  const [showStatement, setShowStatement] = useState(false);
  const [statement, setStatement] = useState<CustomerStatement | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleStatement() {
    // Repli simple si déjà ouvert ; sinon ouverture + chargement à la demande
    // (une seule fois, le relevé est mis en cache local).
    if (showStatement) {
      setShowStatement(false);
      return;
    }
    setShowStatement(true);
    if (statement || loading) return;
    setLoading(true);
    setError(null);
    getCustomerStatement(customerId)
      .then(setStatement)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      )
      .finally(() => setLoading(false));
  }

  return (
    <div className="stagger">
      <div className="panel" style={{ marginBottom: 18 }}>
        <div className="panel__head">
          <div>
            <span className="eyebrow">Client</span>
            <h3 className="panel__title" style={{ marginTop: 4 }}>
              {row.customer.name}
            </h3>
          </div>
          <div className="cellstack" style={{ alignItems: "flex-end" }}>
            {row.blocked_by_payment ? (
              <PaymentBadge />
            ) : (
              <ReminderLevelTag level={row.suggested_level} />
            )}
            <span className="num" style={{ fontSize: 20, fontWeight: 600 }}>
              {money(row.total_due)}
            </span>
          </div>
        </div>
        <div className="panel__body">
          <div className="note" style={{ marginBottom: 14 }}>
            {row.customer.email ? (
              <span className="num">{row.customer.email}</span>
            ) : (
              <em>Aucune adresse e-mail connue.</em>
            )}
            {last ? (
              <>
                {" · "}Dernière relance consignée le{" "}
                <strong>{dateTime(last.sent_at)}</strong>
              </>
            ) : (
              <> · Aucune relance consignée à ce jour.</>
            )}
          </div>
          <InvoiceList invoices={row.open_invoices} today={today} />

          <div style={{ marginTop: 14 }}>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={toggleStatement}
            >
              {showStatement ? "Masquer le relevé" : "Voir le relevé"}
            </button>
          </div>

          {showStatement ? (
            <div style={{ marginTop: 14 }}>
              {loading ? (
                <div className="skel" style={{ height: 200 }} />
              ) : error ? (
                <div className="errbox">Relevé indisponible : {error}</div>
              ) : statement ? (
                <StatementTable statement={statement} />
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      <DraftPanel
        row={row}
        fetchDraft={fetchDraft}
        confirmSent={confirmSent}
        confirming={confirming}
        onConfirmed={onConfirmed}
      />
    </div>
  );
}
