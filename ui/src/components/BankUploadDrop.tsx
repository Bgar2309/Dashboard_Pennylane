// Dépôt d'un relevé bancaire HSBC (xlsx/pdf) : drag & drop ou sélection de
// fichier → uploadBank → affiche les rapprochements transaction ↔ facture
// avec leur niveau de confiance. Lecture/écriture côté API uniquement.

import { useRef, useState } from "react";

import type { PaymentMatch } from "../api-client";
import { useBankUpload } from "../hooks";
import { useToast } from "./Toast";
import { CONF_LABEL, money } from "./format";

const ACCEPT = ".xlsx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

function MatchTable({ matches }: { matches: PaymentMatch[] }) {
  if (matches.length === 0) {
    return <div className="empty">Aucun rapprochement trouvé dans ce relevé.</div>;
  }
  return (
    <table className="tbl">
      <thead>
        <tr>
          <th>Réf. bancaire</th>
          <th>Facture</th>
          <th>Confiance</th>
          <th className="r">Montant</th>
        </tr>
      </thead>
      <tbody>
        {matches.map((m, i) => (
          <tr key={`${m.bank_ref}-${i}`}>
            <td>
              <div className="cust">
                <span className="cust__name num">{m.bank_ref}</span>
                {m.reason ? <span className="cust__meta">{m.reason}</span> : null}
              </div>
            </td>
            <td>
              {m.invoice_number ? (
                <div className="cust">
                  <span className="num">{m.invoice_number}</span>
                  {m.customer_name ? (
                    <span className="cust__meta">{m.customer_name}</span>
                  ) : null}
                </div>
              ) : (
                <span className="cust__meta">— non rapprochée —</span>
              )}
            </td>
            <td>
              <span className={`conf conf-${m.confidence}`}>
                {CONF_LABEL[m.confidence]}
              </span>
            </td>
            <td className="r tbl__amount">{money(m.amount)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function BankUploadDrop() {
  const { matches, loading, error, upload } = useBankUpload();
  const { toast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  async function handleFile(file: File) {
    try {
      const result = await upload(file);
      const matched = result.filter((m) => m.invoice_id !== null).length;
      toast("Relevé analysé", {
        variant: "success",
        message: `${result.length} ligne(s) · ${matched} rapprochée(s) à une facture.`,
      });
    } catch {
      toast("Échec de l'analyse du relevé");
    }
  }

  return (
    <div className="panel">
      <div className="panel__head">
        <h3 className="panel__title">Rapprochement bancaire</h3>
        <span className="eyebrow">HSBC · xlsx / pdf</span>
      </div>
      <div className="panel__body">
        <div
          className={`drop${over ? " drop--over" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setOver(false);
            const file = e.dataTransfer.files?.[0];
            if (file) void handleFile(file);
          }}
        >
          <svg className="drop__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M12 16V4m0 0L8 8m4-4l4 4M5 20h14"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <div className="drop__title">
            {loading ? "Analyse en cours…" : "Déposer un relevé HSBC"}
          </div>
          <div className="drop__hint">
            Glissez le fichier ici ou cliquez pour le sélectionner (.xlsx, .pdf)
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleFile(file);
              e.target.value = "";
            }}
          />
        </div>

        {error ? (
          <div className="errbox" style={{ marginTop: 14 }}>
            {error instanceof Error ? error.message : String(error)}
          </div>
        ) : null}

        {matches ? (
          <div style={{ marginTop: 18 }}>
            <div className="eyebrow" style={{ marginBottom: 10 }}>
              Rapprochements
            </div>
            <MatchTable matches={matches} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
