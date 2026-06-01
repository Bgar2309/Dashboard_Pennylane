// Panneau brouillon : récupère le TEXTE de la relance via getDraft (lecture
// seule, n'écrit rien), l'affiche dans un bloc « papier réglé », et propose le
// bouton « J'ai envoyé cette relance » → confirmSent (seul point d'écriture)
// → toast + rafraîchissement de l'historique.

import { useEffect, useState } from "react";

import type {
  ConfirmSentIn,
  CustomerDunningRow,
  Draft,
  ReminderLogEntry,
} from "../api-client";
import { ReminderLevelTag } from "./ReminderLevelTag";
import { useToast } from "./Toast";
import { LEVEL_LABEL } from "./format";

export function DraftPanel({
  row,
  fetchDraft,
  confirmSent,
  confirming,
  onConfirmed,
}: {
  row: CustomerDunningRow;
  fetchDraft: (customerId: number) => Promise<Draft>;
  confirmSent: (customerId: number, body: ConfirmSentIn) => Promise<ReminderLogEntry>;
  confirming: boolean;
  onConfirmed?: (entry: ReminderLogEntry) => void;
}) {
  const customerId = row.customer.id;
  const blocked = row.blocked_by_payment;

  const [draft, setDraft] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    setDraft(null);
    fetchDraft(customerId)
      .then((d) => {
        if (alive) setDraft(d.draft);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [fetchDraft, customerId]);

  async function handleConfirm() {
    const invoiceNumbers = row.open_invoices.map((i) => i.number);
    try {
      const entry = await confirmSent(customerId, {
        level: row.suggested_level,
        invoice_numbers: invoiceNumbers,
      });
      toast("Relance enregistrée", {
        variant: "success",
        message: `${row.customer.name} · ${LEVEL_LABEL[row.suggested_level]} consignée dans l'historique.`,
      });
      onConfirmed?.(entry);
    } catch (err) {
      toast("Échec de l'enregistrement", {
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }

  return (
    <div className="panel">
      <div className="panel__head">
        <h3 className="panel__title">Brouillon de relance</h3>
        <ReminderLevelTag level={row.suggested_level} />
      </div>
      <div className="panel__body">
        {blocked ? (
          <div className="errbox" style={{ marginBottom: 14 }}>
            Ce client est couvert par un paiement bancaire rapproché : aucune
            relance n'est nécessaire.
          </div>
        ) : null}

        {loading ? (
          <div className="skel" style={{ height: 200 }} />
        ) : error ? (
          <div className="errbox">Brouillon indisponible : {error}</div>
        ) : (
          <pre className="draft">{draft}</pre>
        )}

        <div className="draft__bar">
          <p className="draft__note">
            Le brouillon est généré à la lecture. Rien n'est consigné tant que
            vous n'avez pas confirmé l'envoi.
          </p>
          <button
            type="button"
            className="btn btn--primary"
            disabled={blocked || loading || !!error || confirming}
            onClick={handleConfirm}
          >
            {confirming ? "Enregistrement…" : "J'ai envoyé cette relance"}
          </button>
        </div>
      </div>
    </div>
  );
}
