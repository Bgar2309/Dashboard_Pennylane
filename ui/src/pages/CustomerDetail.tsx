// Panneau détail d'un client sélectionné : en-tête + factures ouvertes
// (InvoiceList) + brouillon de relance (DraftPanel). Le brouillon est lu via
// getDraft (rien n'est consigné), l'envoi confirmé via confirmSent.

import type {
  ConfirmSentIn,
  CustomerDunningRow,
  Draft,
  IsoDate,
  ReminderLogEntry,
} from "../api-client";
import {
  DraftPanel,
  InvoiceList,
  PaymentBadge,
  ReminderLevelTag,
  dateTime,
  money,
} from "../components";

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
