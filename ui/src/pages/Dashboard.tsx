// Tableau de bord : KPIs + répartition d'âge + top retardataires + rapprochement.

import { AgingBar, BankUploadDrop, Card, EmptyState, ErrorState, KpiCard, Loading } from "../components";
import { BucketTag } from "../components/Tags";
import type { AgingBucket } from "../api-client/types";
import { eur, fmtDate } from "../format";
import { useStats } from "../hooks";

export function Dashboard({ today }: { today?: string }) {
  const { data, loading, error, reload } = useStats(today);

  return (
    <div className="reveal">
      <div className="page-head">
        <div>
          <div className="eyebrow">Pilotage du poste client</div>
          <h1>Tableau de bord</h1>
          <p className="lede">
            Encours, ancienneté et clients prioritaires — recoupés avec la banque
            pour ne jamais relancer un paiement déjà reçu.
          </p>
        </div>
        <div className="head-meta">
          <span className="big mono">{today ?? new Date().toLocaleDateString("fr-FR")}</span>
          date d'évaluation
        </div>
      </div>

      {loading && <Card><Loading label="Calcul des indicateurs…" /></Card>}
      {error && <Card><ErrorState message={error} onRetry={reload} /></Card>}

      {data && (
        <>
          <div className="kpi-grid">
            <KpiCard
              label="Encours total"
              value={eur(data.encours_total)}
              sub="reste dû, toutes factures ouvertes"
              accent="var(--ink)"
              delay={0}
            />
            <KpiCard
              label="Clients à relancer"
              value={data.clients_a_relancer}
              sub="hors clients déjà payés en banque"
              accent="var(--vermillion)"
              delay={60}
            />
            <KpiCard
              label="DSO approché"
              value={Math.round(Number(data.dso_approche) || 0)}
              unit="j"
              sub="délai moyen d'encaissement"
              accent="var(--petrol)"
              delay={120}
            />
            <KpiCard
              label="Retard moyen pondéré"
              value={Math.round(Number(data.retard_moyen_pondere) || 0)}
              unit="j"
              sub="pondéré par les montants"
              accent="var(--gold)"
              delay={180}
            />
          </div>

          <div className="grid-2">
            <Card title="Répartition de l'encours par ancienneté">
              <AgingBar buckets={data.total_par_bucket} />
            </Card>

            <Card title="Rapprochement bancaire" hint="HSBC">
              <BankUploadDrop onMatched={reload} />
            </Card>
          </div>

          <Card title="Top retardataires" hint="les plus gros encours en retard" className="mt-24">
            {data.top_overdue.length === 0 ? (
              <EmptyState icon="✓" title="Rien en souffrance">
                Aucun client ne dépasse son échéance pour l'instant.
              </EmptyState>
            ) : (
              <div className="tbl-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Client</th>
                      <th>Âge max</th>
                      <th>Plus ancienne échéance</th>
                      <th className="num">Encours dû</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_overdue.map((t, i) => (
                      <tr key={t.customer_id}>
                        <td className="rank">{i + 1}</td>
                        <td>
                          <div className="cust-name">{t.customer_name}</div>
                          <div className="cust-sub">
                            {t.open_invoices_count} facture{t.open_invoices_count > 1 ? "s" : ""} ouverte{t.open_invoices_count > 1 ? "s" : ""}
                          </div>
                        </td>
                        <td><BucketTag bucket={t.worst_bucket as AgingBucket} /></td>
                        <td className="mono muted">{fmtDate(t.oldest_due_date)}</td>
                        <td className="num mono" style={{ fontWeight: 600 }}>{eur(t.total_due)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
