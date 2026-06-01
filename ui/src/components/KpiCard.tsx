// Carte KPI : grand chiffre Fraunces + libellé + sous-texte, liseré coloré.

import type { CSSProperties, ReactNode } from "react";

export function KpiCard({
  label,
  value,
  unit,
  sub,
  accent = "var(--petrol)",
  delay = 0,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  sub?: ReactNode;
  accent?: string;
  delay?: number;
}) {
  const style = { "--accent": accent, animationDelay: `${delay}ms` } as CSSProperties;
  return (
    <div className="kpi reveal" style={style}>
      <div className="k-label">{label}</div>
      <div className="k-value mono">
        {value}
        {unit && <span className="unit">{unit}</span>}
      </div>
      {sub && <div className="k-sub">{sub}</div>}
    </div>
  );
}
