// Page Dashboard : KPIs de l'encours + barre d'âge + top des retardataires,
// et le dépôt de relevé bancaire pour le rapprochement.

import type { IsoDate, TopOverdueItem } from "../api-client";
import {
  AgingBar,
  BankUploadDrop,
  KpiCard,
  date,
  days,
  money,
  moneyCompact,
} from "../components";
import { useStats } from "../hooks";

function TopOverdueTable({ items }: { items: TopOverdueItem[] }) {
  if (items.length === 0) {
    return <div className="empty">Aucun client en retard. 🎉</div>;
  }
  return (
    <table className="tbl">
      <thead>
        <tr>
          <th>Client</th>
          <th>Échéance la + ancienne</th>
          <th className="r">Encours dû</th>
        </tr>
      </thead>
      <tbody>
        {items.map((it) => (
          <tr key={it.customer_id}>
            <td>
              <div className="cust">
                <span className="cust__name">{it.customer_name}</span>
                <span className="cust__meta">
                  {it.open_invoices_count} facture
                  {it.open_invoices_count > 1 ? "s" : ""} · tranche {it.worst_bucket}
                </span>
              </div>
            </td>
            <td className="num">{date(it.oldest_due_date)}</td>
            <td className="r tbl__amount">{money(it.total_due)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Dashboard({ today }: { today: IsoDate }) {
  const { data, loading, error } = useStats(today);

  if (error) {
    return <div className="errbox">Impossible de charger les indicateurs : {error.message}</div>;
  }

  if (loading || !data) {
    return (
      <div className="grid grid--cards">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skel" style={{ height: 132 }} />
        ))}
      </div>
    );
  }

  return (
    <>
      <div className="grid grid--cards stagger">
        <KpiCard
          tone="accent"
          label="Encours total"
          value={moneyCompact(data.encours_total)}
          foot={<span className="num">{money(data.encours_total)}</span>}
        />
        <KpiCard
          tone="rust"
          label="Clients à relancer"
          value={data.clients_a_relancer}
          foot="hors paiements rapprochés"
        />
        <KpiCard
          tone="gold"
          label="DSO approché"
          value={days(data.dso_approche)}
          foot="délai moyen de paiement"
        />
        <KpiCard
          tone="sage"
          label="Retard moyen pondéré"
          value={days(data.retard_moyen_pondere)}
          foot="pondéré par les montants dus"
        />
      </div>

      <div className="grid grid--dash section">
        <div className="reveal">
          <div className="panel" style={{ marginBottom: 18 }}>
            <div className="panel__head">
              <h3 className="panel__title">Encours par âge</h3>
              <span className="eyebrow">balance âgée</span>
            </div>
            <div className="panel__body">
              <AgingBar totals={data.total_par_bucket} />
            </div>
          </div>

          <div className="panel">
            <div className="panel__head">
              <h3 className="panel__title">Top des retardataires</h3>
              <span className="eyebrow">{data.top_overdue.length} clients</span>
            </div>
            <div className="panel__body panel__body--flush">
              <TopOverdueTable items={data.top_overdue} />
            </div>
          </div>
        </div>

        <div className="reveal">
          <BankUploadDrop />
        </div>
      </div>
    </>
  );
}
