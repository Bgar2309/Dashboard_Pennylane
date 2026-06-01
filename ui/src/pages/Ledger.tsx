// Grand livre client : liste à relancer + clients payés (banque), sélection → détail.
// S'appuie sur la vue « reminders » (aging enrichi banque + anti-spam historique).

import { useMemo, useState } from "react";

import { Card, CustomerTable, EmptyState, ErrorState, Loading } from "../components";
import { CustomerDetail } from "./CustomerDetail";
import { eur } from "../format";
import { useReminders } from "../hooks";

export function Ledger({ today }: { today?: string }) {
  const { data, loading, error, reload } = useReminders(today);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { toDun, blocked } = useMemo(() => {
    const rows = data ?? [];
    return {
      toDun: rows.filter((r) => !r.blocked_by_payment),
      blocked: rows.filter((r) => r.blocked_by_payment),
    };
  }, [data]);

  const selected = useMemo(
    () => (data ?? []).find((r) => r.customer.id === selectedId) ?? null,
    [data, selectedId]
  );

  const totalToDun = useMemo(
    () => toDun.reduce((s, r) => s + (typeof r.total_due === "number" ? r.total_due : parseFloat(r.total_due) || 0), 0),
    [toDun]
  );

  if (selected) {
    return (
      <CustomerDetail
        row={selected}
        today={today}
        onBack={() => setSelectedId(null)}
        onConfirmed={() => {
          reload();
          setSelectedId(null);
        }}
      />
    );
  }

  return (
    <div className="reveal">
      <div className="page-head">
        <div>
          <div className="eyebrow">Poste client détaillé</div>
          <h1>Grand livre</h1>
          <p className="lede">
            Sélectionnez un client pour consulter ses factures ouvertes et
            préparer une relance. Les clients déjà payés en banque sont écartés
            de la liste à relancer.
          </p>
        </div>
        {data && (
          <div className="head-meta">
            <span className="big mono">{eur(totalToDun)}</span>
            {toDun.length} client{toDun.length > 1 ? "s" : ""} à relancer
          </div>
        )}
      </div>

      {loading && <Card><Loading label="Chargement du grand livre…" /></Card>}
      {error && <Card><ErrorState message={error} onRetry={reload} /></Card>}

      {data && (
        <div className="stack">
          <Card title="À relancer" hint={`${toDun.length} client${toDun.length > 1 ? "s" : ""}`}>
            {toDun.length === 0 ? (
              <EmptyState icon="✓" title="Aucune relance en attente">
                Tout est à jour, ou les clients concernés ont déjà été relancés récemment.
              </EmptyState>
            ) : (
              <CustomerTable rows={toDun} selectedId={selectedId} onSelect={(r) => setSelectedId(r.customer.id)} />
            )}
          </Card>

          {blocked.length > 0 && (
            <Card
              title="Payés en banque"
              hint="rapprochés — sortis de la liste à relancer"
            >
              <CustomerTable rows={blocked} selectedId={selectedId} onSelect={(r) => setSelectedId(r.customer.id)} />
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
