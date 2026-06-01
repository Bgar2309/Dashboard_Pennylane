// Page Historique : journal des relances consignées (plus récent d'abord).
// Se rafraîchit lorsque `refreshKey` change (après une confirmation d'envoi).

import { useEffect } from "react";

import { ReminderLevelTag, dateTime } from "../components";
import { useHistory } from "../hooks";

export function History({ refreshKey = 0 }: { refreshKey?: number }) {
  const { data, loading, error, refresh } = useHistory({ limit: 200 });

  useEffect(() => {
    if (refreshKey > 0) refresh();
  }, [refreshKey, refresh]);

  const entries = data ?? [];

  return (
    <div className="panel reveal">
      <div className="panel__head">
        <h3 className="panel__title">Journal des relances</h3>
        <span className="eyebrow">
          {loading ? "chargement…" : `${entries.length} entrées`}
        </span>
      </div>
      <div className="panel__body panel__body--flush">
        {error ? (
          <div className="errbox" style={{ margin: 16 }}>
            Impossible de charger l'historique : {error.message}
          </div>
        ) : loading ? (
          <div className="skel" style={{ height: 300, margin: 16 }} />
        ) : entries.length === 0 ? (
          <div className="empty">Aucune relance consignée pour l'instant.</div>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th>Date d'envoi</th>
                <th>Client</th>
                <th>Niveau</th>
                <th>Factures</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id}>
                  <td className="num">{dateTime(e.sent_at)}</td>
                  <td>
                    <span className="cust__name">{e.customer_name}</span>
                  </td>
                  <td>
                    <ReminderLevelTag level={e.level} />
                  </td>
                  <td className="num" style={{ fontSize: 12 }}>
                    {e.invoice_numbers.length > 0
                      ? e.invoice_numbers.join(", ")
                      : "—"}
                  </td>
                  <td className="note" style={{ fontSize: 12.5 }}>
                    {e.note ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
