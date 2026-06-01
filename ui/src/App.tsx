// Coquille de l'application : barre latérale « Le Grand Livre » + navigation
// par hash (Dashboard / Grand livre / Historique) + toaster global.

import { useEffect, useState } from "react";

import { Icon, Toaster } from "./components";
import { Dashboard, History, Ledger } from "./pages";
import { useReminders } from "./hooks";

type Route = "dashboard" | "ledger" | "history";

const ROUTES: { id: Route; label: string; icon: string }[] = [
  { id: "dashboard", label: "Tableau de bord", icon: "dashboard" },
  { id: "ledger", label: "Grand livre", icon: "ledger" },
  { id: "history", label: "Historique", icon: "history" },
];

function currentRoute(): Route {
  const h = window.location.hash.replace("#/", "");
  return (ROUTES.find((r) => r.id === h)?.id ?? "dashboard") as Route;
}

export default function App() {
  const [route, setRoute] = useState<Route>(currentRoute());

  useEffect(() => {
    const onHash = () => setRoute(currentRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  function go(r: Route) {
    window.location.hash = `#/${r}`;
    setRoute(r);
  }

  // Compteur de clients à relancer pour le badge de navigation.
  const { data: reminders } = useReminders();
  const toDunCount = (reminders ?? []).filter((r) => !r.blocked_by_payment).length;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="mark">
            Le Grand<br />
            <em>Livre</em>
          </span>
          <span className="sub">Relance EHS</span>
        </div>

        <div className="nav-section">Navigation</div>
        {ROUTES.map((r) => (
          <button
            key={r.id}
            className={`nav-item ${route === r.id ? "active" : ""}`}
            onClick={() => go(r.id)}
          >
            <span className="nav-ico"><Icon name={r.icon} size={18} /></span>
            {r.label}
            {r.id === "ledger" && toDunCount > 0 && (
              <span className="badge-n">{toDunCount}</span>
            )}
          </button>
        ))}

        <div className="sidebar-foot">
          <strong>Pennylane</strong> — vérité comptable, lecture seule.<br />
          Rapprochement <strong>HSBC</strong> local pour ne jamais relancer un
          paiement déjà reçu.
        </div>
      </aside>

      <main className="main">
        {route === "dashboard" && <Dashboard />}
        {route === "ledger" && <Ledger />}
        {route === "history" && <History />}
      </main>

      <Toaster />
    </div>
  );
}
