// Page Grand livre : table des clients (CustomerTable) en maître, détail du
// client sélectionné (CustomerDetail) à droite. La sélection ouvre le panneau
// factures + brouillon ; la confirmation d'envoi rafraîchit la vue.

import { useMemo, useState } from "react";

import type { IsoDate, ReminderLogEntry } from "../api-client";
import { CustomerTable } from "../components";
import { useReminders } from "../hooks";
import { CustomerDetail } from "./CustomerDetail";

export function Ledger({
  today,
  onReminderSent,
}: {
  today: IsoDate;
  onReminderSent?: (entry: ReminderLogEntry) => void;
}) {
  const { data, loading, error, fetchDraft, confirmSent, confirming } =
    useReminders(today);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const rows = data ?? [];
  const selected = useMemo(
    () => rows.find((r) => r.customer.id === selectedId) ?? null,
    [rows, selectedId],
  );

  return (
    <div className="grid grid--detail">
      <div className="panel reveal">
        <div className="panel__head">
          <h3 className="panel__title">Clients à relancer</h3>
          <span className="eyebrow">
            {loading ? "chargement…" : `${rows.length} clients`}
          </span>
        </div>
        <div className="panel__body panel__body--flush">
          {error ? (
            <div className="errbox" style={{ margin: 16 }}>
              Impossible de charger le grand livre : {error.message}
            </div>
          ) : loading ? (
            <div className="skel" style={{ height: 320, margin: 16 }} />
          ) : (
            <CustomerTable
              rows={rows}
              selectedId={selectedId}
              onSelect={(r) => setSelectedId(r.customer.id)}
            />
          )}
        </div>
      </div>

      {selected ? (
        <CustomerDetail
          key={selected.customer.id}
          row={selected}
          today={today}
          fetchDraft={fetchDraft}
          confirmSent={confirmSent}
          confirming={confirming}
          onConfirmed={onReminderSent}
        />
      ) : (
        <div className="panel reveal">
          <div className="panel__body empty" style={{ padding: "64px 24px" }}>
            Sélectionnez un client dans le grand livre pour consulter ses
            factures et préparer sa relance.
          </div>
        </div>
      )}
    </div>
  );
}
