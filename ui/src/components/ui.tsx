// Primitives partagées : Card, états (chargement / erreur / vide), Icon, Toaster.

import type { ReactNode } from "react";
import { dismissToast, useToasts } from "../hooks";

export function Card({
  title,
  hint,
  action,
  children,
  className = "",
}: {
  title?: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card card-pad ${className}`}>
      {(title || action) && (
        <div className="card-title" style={{ marginBottom: 16 }}>
          <span>
            {title}
            {hint && <span className="hint" style={{ marginLeft: 8 }}>{hint}</span>}
          </span>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Loading({ label = "Chargement…" }: { label?: string }) {
  return (
    <div className="state">
      <div className="spinner" />
      <div className="muted">{label}</div>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state">
      <div className="st-ico">⚠</div>
      <div className="st-title">Impossible de charger</div>
      <div className="muted" style={{ maxWidth: "42ch" }}>{message}</div>
      {onRetry && (
        <button className="btn" style={{ marginTop: 6 }} onClick={onRetry}>
          Réessayer
        </button>
      )}
    </div>
  );
}

export function EmptyState({ icon = "—", title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="state">
      <div className="st-ico">{icon}</div>
      <div className="st-title">{title}</div>
      {children && <div className="muted" style={{ maxWidth: "44ch" }}>{children}</div>}
    </div>
  );
}

// --- Icônes (line-art, héritent de currentColor) ---

const PATHS: Record<string, ReactNode> = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </>
  ),
  ledger: (
    <>
      <path d="M5 4h11a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2V4Z" />
      <path d="M5 4a2 2 0 0 0-2 2v12" />
      <path d="M9 9h6M9 13h6" />
    </>
  ),
  history: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7v5l3.5 2" />
    </>
  ),
  bank: (
    <>
      <path d="M3 9 12 4l9 5" />
      <path d="M5 9v8M19 9v8M9 9v8M15 9v8" />
      <path d="M3 20h18" />
    </>
  ),
  send: (
    <>
      <path d="M21 4 3 11l6 2 2 6 10-15Z" />
      <path d="M9 13 21 4" />
    </>
  ),
  check: <path d="M4 12.5 9.5 18 20 6" />,
  arrowLeft: <path d="M15 5l-7 7 7 7" />,
};

export function Icon({ name, size = 18 }: { name: keyof typeof PATHS | string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name] ?? null}
    </svg>
  );
}

export function Toaster() {
  const toasts = useToasts();
  const glyph: Record<string, string> = { success: "✓", error: "✕", info: "•" };
  return (
    <div className="toaster">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`} onClick={() => dismissToast(t.id)}>
          <span className="t-ico">{glyph[t.kind]}</span>
          <span>{t.message}</span>
        </div>
      ))}
    </div>
  );
}
