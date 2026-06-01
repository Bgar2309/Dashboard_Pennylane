// Shell de l'application « Le Grand Livre » : tranche de navigation à gauche,
// page courante à droite. La confirmation d'une relance (depuis le Grand
// livre) déclenche un toast et le rafraîchissement de l'Historique.

import { useMemo, useState } from "react";

import { ToastProvider } from "./components";
import { Dashboard, History, Ledger } from "./pages";

type Route = "dashboard" | "ledger" | "history";

const NAV: { id: Route; no: string; label: string }[] = [
  { id: "dashboard", no: "01", label: "Tableau de bord" },
  { id: "ledger", no: "02", label: "Grand livre" },
  { id: "history", no: "03", label: "Historique" },
];

const MASTHEAD: Record<Route, { title: string; lede: string }> = {
  dashboard: {
    title: "Tableau de bord",
    lede: "Encours, balance âgée et clients à relancer en priorité. Déposez un relevé HSBC pour rapprocher les paiements reçus.",
  },
  ledger: {
    title: "Grand livre",
    lede: "Sélectionnez un client pour consulter ses factures ouvertes et préparer sa relance. Rien n'est envoyé sans votre confirmation.",
  },
  history: {
    title: "Historique",
    lede: "Journal des relances que vous avez confirmées comme envoyées.",
  },
};

export default function App() {
  const [route, setRoute] = useState<Route>("dashboard");
  const [historyKey, setHistoryKey] = useState(0);

  const today = useMemo(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
      d.getDate(),
    ).padStart(2, "0")}`;
  }, []);

  const todayLabel = useMemo(
    () =>
      new Intl.DateTimeFormat("fr-FR", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      }).format(new Date()),
    [],
  );

  const head = MASTHEAD[route];

  return (
    <ToastProvider>
      <div className="app">
        <aside className="rail">
          <div className="rail__brand">
            <span className="rail__mark">
              Relance <em>EHS</em>
            </span>
            <span className="rail__sub">Le Grand Livre</span>
          </div>
          <nav className="rail__nav">
            {NAV.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`navitem${route === item.id ? " navitem--active" : ""}`}
                onClick={() => setRoute(item.id)}
              >
                <span className="navitem__no">{item.no}</span>
                {item.label}
              </button>
            ))}
          </nav>
          <div className="rail__foot">
            <strong>Recouvrement clients</strong>
            <br />
            Suivi de l'encours et des relances — données Pennylane,
            rapprochement HSBC.
          </div>
        </aside>

        <main className="main">
          <header className="masthead">
            <div>
              <h1 className="masthead__title">{head.title}</h1>
              <p className="masthead__lede">{head.lede}</p>
            </div>
            <div className="masthead__date">
              <div className="eyebrow">Arrêté au</div>
              <div className="num" style={{ textTransform: "capitalize" }}>
                {todayLabel}
              </div>
            </div>
          </header>

          {route === "dashboard" ? (
            <Dashboard today={today} />
          ) : route === "ledger" ? (
            <Ledger
              today={today}
              onReminderSent={() => setHistoryKey((k) => k + 1)}
            />
          ) : (
            <History refreshKey={historyKey} />
          )}
        </main>
      </div>
    </ToastProvider>
  );
}
