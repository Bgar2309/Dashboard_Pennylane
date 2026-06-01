// Historique des relances consignées (POST /confirm). Lecture seule.

import { Card, EmptyState, ErrorState, Loading } from "../components";
import { ReminderLevelTag } from "../components/Tags";
import { fmtDateTime } from "../format";
import { useHistory } from "../hooks";

export function History() {
  const { data, loading, error, reload } = useHistory();

  return (
    <div className="reveal">
      <div className="page-head">
        <div>
          <div className="eyebrow">Journal des relances</div>
          <h1>Historique</h1>
          <p className="lede">
            Chaque ligne correspond à une relance confirmée comme envoyée. Rien
            n'est consigné automatiquement — uniquement sur action explicite.
          </p>
        </div>
        {data && (
          <div className="head-meta">
            <span className="big mono">{data.length}</span>
            relance{data.length > 1 ? "s" : ""} consignée{data.length > 1 ? "s" : ""}
          </div>
        )}
      </div>

      <Card>
        {loading && <Loading label="Chargement de l'historique…" />}
        {error && <ErrorState message={error} onRetry={reload} />}
        {data && data.length === 0 && (
          <EmptyState icon="✦" title="Aucune relance consignée">
            Les relances que vous confirmez depuis le grand livre apparaîtront ici.
          </EmptyState>
        )}
        {data && data.length > 0 && (
          <div className="tbl-wrap">
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
                {data.map((e) => (
                  <tr key={e.id}>
                    <td className="mono muted">{fmtDateTime(e.sent_at)}</td>
                    <td className="cust-name">{e.customer_name}</td>
                    <td><ReminderLevelTag level={e.level} /></td>
                    <td className="mono">
                      {e.invoice_numbers.length > 0 ? e.invoice_numbers.join(", ") : "—"}
                    </td>
                    <td className="muted">{e.note || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
