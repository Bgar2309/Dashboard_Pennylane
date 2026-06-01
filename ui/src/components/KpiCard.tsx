// Carte KPI : libellé en petites capitales + valeur en chiffres tabulaires,
// liseré coloré en haut selon la tonalité.

import type { ReactNode } from "react";

export type KpiTone = "accent" | "sage" | "gold" | "rust";

export function KpiCard({
  label,
  value,
  unit,
  foot,
  tone = "accent",
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  foot?: ReactNode;
  tone?: KpiTone;
}) {
  return (
    <article className={`kpi kpi--${tone}`}>
      <p className="kpi__label">{label}</p>
      <div className="kpi__value">
        {value}
        {unit ? <span className="unit">{unit}</span> : null}
      </div>
      {foot ? <div className="kpi__foot">{foot}</div> : null}
    </article>
  );
}
