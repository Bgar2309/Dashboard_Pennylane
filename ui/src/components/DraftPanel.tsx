// Panneau brouillon de relance.
//   - charge le texte via getDraft (LECTURE SEULE : n'écrit rien) ;
//   - bouton « J'ai envoyé cette relance » → confirmSent (SEUL point d'écriture)
//     → toast + callback de rafraîchissement de l'historique.

import { useState } from "react";

import { api, ApiError } from "../api-client/client";
import type { CustomerDunningRow } from "../api-client/types";
import { LEVEL_LABEL } from "../api-client/types";
import { pushToast, useDraft } from "../hooks";
import { Icon, Loading } from "./ui";
import { PaymentBadge, ReminderLevelTag } from "./Tags";

export function DraftPanel({
  row,
  today,
  onConfirmed,
}: {
  row: CustomerDunningRow;
  today?: string;
  onConfirmed?: () => void;
}) {
  const { data, loading, error } = useDraft(row.customer.id, today);
  const [sending, setSending] = useState(false);

  const invoiceNumbers = row.open_invoices.map((i) => i.number);
  const blocked = row.blocked_by_payment;

  async function handleConfirm() {
    setSending(true);
    try {
      await api.confirmSent(row.customer.id, {
        level: row.suggested_level,
        invoice_numbers: invoiceNumbers,
        note: null,
      });
      pushToast(
        `Relance « ${LEVEL_LABEL[row.suggested_level]} » consignée pour ${row.customer.name}.`,
        "success"
      );
      onConfirmed?.();
    } catch (e) {
      pushToast(e instanceof ApiError ? e.message : "Échec de l'enregistrement.", "error");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="card card-pad">
      <div className="card-title" style={{ marginBottom: 14 }}>
        <span>Brouillon de relance</span>
        <ReminderLevelTag level={row.suggested_level} />
      </div>

      {blocked && (
        <div className="error-banner" style={{ marginBottom: 14, background: "#e3f0ec", color: "var(--petrol)", borderColor: "rgba(31,106,94,.3)" }}>
          Paiement détecté en banque — ce client est sorti de la liste à relancer.
        </div>
      )}

      {loading && <Loading label="Génération du brouillon…" />}
      {error && <div className="error-banner">{error}</div>}
      {!loading && !error && (
        <>
          <div className="draft-letter">{data?.draft || "—"}</div>

          <div className="row-between mt-16">
            <span className="muted" style={{ fontSize: 12 }}>
              {invoiceNumbers.length} facture{invoiceNumbers.length > 1 ? "s" : ""} ·
              généré à la volée, rien n'est envoyé automatiquement.
            </span>
            {blocked ? (
              <PaymentBadge />
            ) : (
              <button
                className="btn btn-primary"
                onClick={handleConfirm}
                disabled={sending || !data?.draft}
              >
                <Icon name={sending ? "send" : "check"} size={16} />
                {sending ? "Enregistrement…" : "J'ai envoyé cette relance"}
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
}
