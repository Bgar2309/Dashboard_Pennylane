// Dépôt d'un relevé bancaire HSBC (xlsx/pdf) → uploadBank → affiche les matchs.

import { useRef, useState } from "react";

import type { PaymentMatch } from "../api-client/types";
import { eur2 } from "../format";
import { pushToast, useBankUpload } from "../hooks";
import { ConfidenceTag } from "./Tags";
import { Icon } from "./ui";

const ACCEPT = ".xlsx,.xls,.pdf";

export function BankUploadDrop({ onMatched }: { onMatched?: (m: PaymentMatch[]) => void }) {
  const { matches, loading, error, lastFile, upload } = useBankUpload();
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    const res = await upload(file);
    if (res) {
      const strong = res.filter((m) => m.confidence !== "none").length;
      pushToast(
        `${file.name} analysé — ${strong} rapprochement${strong > 1 ? "s" : ""} sur ${res.length} ligne${res.length > 1 ? "s" : ""}.`,
        "success"
      );
      onMatched?.(res);
    }
  }

  return (
    <div className="stack">
      <div
        className={`dropzone ${dragging ? "drag" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files?.[0];
          if (f) void handleFile(f);
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void handleFile(f);
            e.target.value = "";
          }}
        />
        <div className="dz-ico" style={{ color: "var(--petrol)" }}>
          <Icon name="bank" size={30} />
        </div>
        <div className="dz-title">
          {loading ? "Analyse en cours…" : "Déposer un relevé HSBC"}
        </div>
        <div className="dz-sub">
          {loading
            ? "Parsing + rapprochement des factures ouvertes"
            : "Glissez un fichier .xlsx ou .pdf, ou cliquez pour parcourir"}
        </div>
        {lastFile && !loading && (
          <div className="dz-sub" style={{ marginTop: 8, color: "var(--petrol)" }}>
            Dernier fichier : {lastFile}
          </div>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {matches && matches.length > 0 && (
        <div className="tbl-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>Réf. banque</th>
                <th>Client / facture</th>
                <th>Confiance</th>
                <th className="num">Montant</th>
              </tr>
            </thead>
            <tbody>
              {matches.map((m, i) => (
                <tr key={`${m.bank_ref}-${i}`}>
                  <td className="mono">{m.bank_ref}</td>
                  <td>
                    <div className="cust-name">{m.customer_name ?? "—"}</div>
                    <div className="cust-sub">
                      {m.matched_invoice_numbers.length > 0
                        ? m.matched_invoice_numbers.join(", ")
                        : m.reason || "Aucune facture rapprochée"}
                    </div>
                  </td>
                  <td><ConfidenceTag confidence={m.confidence} /></td>
                  <td className="num mono" style={{ fontWeight: 600 }}>{eur2(m.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {matches && matches.length === 0 && (
        <div className="muted">Aucune ligne de crédit exploitable dans ce relevé.</div>
      )}
    </div>
  );
}
