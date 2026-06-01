# AGENTS.md — Relance EHS

Mode d'emploi : ouvre N terminaux Claude Code à la racine `relance-ehs/`. Lance les agents
**par vague**. Au sein d'une vague, tous tournent EN PARALLÈLE. Entre deux vagues : attendre
que tout soit fini + tests verts + commit, puis lancer la vague suivante.

`core/` est DÉJÀ implémenté (models.py + aging.py). Ne pas le réimplémenter.

Règles communes à TOUS les agents :
- Tu travailles EXCLUSIVEMENT dans ton dossier. Lecture autorisée partout, écriture restreinte.
- Les interfaces d'ARCHITECTURE.md sont gravées. Si tu veux en changer une → `INTERFACE_CHANGE_REQUEST.md`, tu n'y touches pas seul.
- Si un module dont tu dépends n'est pas prêt, tu le mockes selon l'interface (`# MOCK:`).
- ❌ pas de pandas-ta/ta-lib · ❌ pas de print() (logging) · ❌ pas de secret hardcodé (config.py)
- ✅ type hints + docstrings sur tout public · ✅ commit `feat(<module>): implémentation initiale`

---

## VAGUE 1 — parallèle (4 agents)

### Agent A — `storage`
```
Contexte : Relance EHS, dashboard de relance client (Pennylane lecture seule + rapprochement
HSBC local). Stack FastAPI + SQLite. Voir ARCHITECTURE.md.

Périmètre : EXCLUSIVEMENT backend/storage/. Lecture seule sur backend/core/.

Implémente la classe Storage (backend/storage/db.py) selon l'interface gravée dans son README
et ARCHITECTURE.md. SQLite via sqlite3 stdlib. db_path depuis config.DATABASE_PATH si None.
Tables : reminders_log, payment_matches, invoice_cache, cache_meta. Sérialise invoice_numbers
en JSON. log_reminder est le SEUL point d'écriture de l'historique.

Tâches : init_schema idempotent ; log_reminder/get_last_reminder/list_reminders ;
save_matches/list_matches/clear_matches ; cache_invoices/get_cached_invoices/cache_age_seconds.
Tests dans backend/tests/test_storage.py (DB en tmpfile). Critère de fin : pytest vert.
```

### Agent B — `integration/pennylane`
```
Contexte : idem. Voir ARCHITECTURE.md + backend/integration/pennylane/README.md.

Périmètre : EXCLUSIVEMENT backend/integration/pennylane/. Lecture seule sur backend/core/.

OBLIGATOIRE avant de coder : lire https://pennylane.readme.io/reference pour les NOMS DE
CHAMPS EXACTS des endpoints /customer_invoices, /customers, /transactions de l'API v2, et le
mécanisme de pagination (cursor / has_more). Ne devine pas les champs.

Implémente PennylaneClient (httpx) : Bearer token = config.PENNYLANE_TOKEN. LECTURE SEULE,
aucun POST/PUT/DELETE. Pagine TOUT. Mappe le JSON vers core.Invoice/Customer/BankTransaction.
list_open_invoices = factures avec remaining_amount > 0. list_bank_transactions -> source='revolut'.

Tests : mock httpx (respx ou monkeypatch) avec des payloads d'exemple. Critère : pytest vert,
aucun appel réseau réel en test.
```

### Agent C — `integration/hsbc_parser`
```
Contexte : idem. Voir backend/integration/hsbc_parser/README.md.

Périmètre : EXCLUSIVEMENT backend/integration/hsbc_parser/. Lecture seule sur backend/core/.

Implémente parse_hsbc_xlsx (openpyxl/pandas) et parse_hsbc_pdf (pdfplumber) -> list[BankTransaction].
Le parser est NEUTRE : il rend TOUTES les lignes de mouvement, ne filtre pas interne/frais.
Colonnes XLSX : "Libellé", "Référence client", "Montant du crédit", "Montant du débit",
"Date de valeur", "Date opération", "Référence bancaire". Ignore les en-têtes de compte répétés.
Normalise l'encodage (remplacer les '?' parasites par espace). Dates DD/MM/YYYY -> date.
credit rempli -> credit ; débit -> debit. source='hsbc'.

Tests : un XLSX d'exemple est fourni dans backend/tests/fixtures/ (demande à Bruno de déposer
le fichier HSBC réel anonymisé, ou génère un mini-XLSX au format décrit). Critère : pytest vert,
les virements internes (EHS GROUP FRANCE/Treso) et frais sont bien présents dans le retour
(le parser ne les exclut PAS — c'est voulu).
```

### Agent D — `service/reminders/drafts`
```
Contexte : idem. Voir backend/service/reminders/README.md.

Périmètre : EXCLUSIVEMENT backend/service/reminders/drafts.py. Lecture seule sur backend/core/.
NE TOUCHE PAS à service/reminders/service.py (c'est un autre agent, vague 3).

Implémente DraftGenerator.render(customer, invoices, level, today) -> str. Templates FR
déterministes (pas de LLM). 3 tons : FIRST (rappel courtois), SECOND (relance ferme),
FORMAL (mise en demeure). Inclure un tableau texte des factures dues (numéro, date, échéance,
montant, reste dû) et le total. Texte prêt à copier-coller dans un mail.

Tests : test_drafts.py vérifie qu'un client + 2 factures + chaque niveau produit un texte
non vide contenant les numéros de facture et le total. Critère : pytest vert.
```

→ Après vague 1 : `cd backend && pip install -r requirements.txt && pytest backend/tests/` doit être vert. Commit.

---

## VAGUE 2 — parallèle (3 agents) — après vague 1

### Agent E — `service/ledger`
```
Contexte : idem. Voir backend/service/ledger/README.md. core, storage, integration/pennylane sont prêts.

Périmètre : EXCLUSIVEMENT backend/service/ledger/.

Implémente LedgerService(pennylane, storage). get_open_invoices avec cache (storage,
max_cache_age_s). aging_for utilise core.bucket_for. build_dunning_rows agrège par client :
total_due, oldest_due_date, worst_bucket, suggested_level (core.level_for SANS historique ni
banque ici — last_reminder=None, blocked_by_payment=False ; reminders affinera).

Tests : injecter un faux PennylaneClient et un faux Storage (ou réels en tmpfile). Critère : pytest vert.
```

### Agent F — `service/bank_match`
```
Contexte : idem. Voir backend/service/bank_match/README.md + filters.py. core, storage prêts.

Périmètre : EXCLUSIVEMENT backend/service/bank_match/.

Implémente BankMatchService(storage). is_client_payment : True si credit>0 ET libellé ne
contient AUCUN motif de filters.INTERNAL_LABELS / FEE_LABELS (insensible casse/espaces).
extract_invoice_numbers : regex filters.INVOICE_NUMBER_REGEX sur le libellé -> liste de numéros.
match : 3 niveaux — STRONG (numéro facture trouvé ET montant ≈ à ±1% ou ±1€), MEDIUM (nom client
fuzzy via rapidfuzz >= 85 ET montant exact), WEAK (montant exact seul). Renseigne reason lisible.
covered_invoice_ids -> ids des factures matchées STRONG/MEDIUM (pas WEAK).

Tests : utilise des BankTransaction inspirées du relevé réel (GALLIN 260604, SIGNAL CONCEPT 260864,
le virement interne EHS GROUP FRANCE/Treso doit être REJETÉ par is_client_payment). Critère : pytest vert.
```

### Agent G — `service/stats`
```
Contexte : idem. Voir backend/service/stats/README.md. core, storage, service/ledger prêts.

Périmètre : EXCLUSIVEMENT backend/service/stats/.

Implémente StatsService(ledger, storage). dashboard_kpis : encours total, nb clients à relancer,
DSO approché, retard moyen pondéré, total par bucket. aging_distribution : {bucket: montant}.
top_overdue : n clients par total_due décroissant. Consomme des CustomerDunningRow, ne recalcule
pas l'aging brut.

Tests : passer une liste de CustomerDunningRow construites à la main. Critère : pytest vert.
```

→ Après vague 2 : pytest vert sur ledger, bank_match, stats. Commit.

---

## VAGUE 3 — 1 agent — après vague 2

### Agent H — `service/reminders` (orchestrateur)
```
Contexte : idem. Voir backend/service/reminders/README.md. ledger, bank_match, drafts, storage prêts.

Périmètre : EXCLUSIVEMENT backend/service/reminders/service.py (NE touche pas drafts.py).

Implémente ReminderService(ledger, bank_match, storage, drafts).
dunning_view : part de ledger.build_dunning_rows, applique le blocage paiement
(bank_match.covered_invoice_ids sur HSBC txs passés + Revolut via pennylane) -> blocked_by_payment,
enrichit last_reminder (storage.get_last_reminder) et ajuste suggested_level (core.level_for avec
historique), et masque/abaisse les clients relancés depuis < min_days_between_reminders.
generate_draft : appelle drafts.render. NE LOGUE RIEN.
confirm_sent : storage.log_reminder. SEULE méthode qui écrit l'historique.

Tests : faux services + storage tmpfile. Vérifie qu'un client couvert par un match HSBC a
blocked_by_payment=True, que generate_draft n'écrit rien, que confirm_sent crée bien une entrée.
Critère : pytest vert.
```

→ Commit.

---

## VAGUE 4 — parallèle (2 agents) — après vague 3

### Agent I — `api/schemas.py` + `api/deps.py` + `api/main.py` (socle, à finir EN PREMIER)
```
Contexte : idem. Voir backend/api/README.md + ARCHITECTURE.md (liste endpoints).

Périmètre : backend/api/schemas.py, backend/api/deps.py, backend/api/main.py UNIQUEMENT.
NE touche pas aux routers (autres agents). Mais comme les routers dépendent de toi, FINIS VITE
et commit avant que I-bis démarre les routers (ou fais routers ensuite toi-même).

schemas.py : Pydantic miroir de core (InvoiceOut, CustomerDunningRowOut, PaymentMatchOut,
ReminderLogEntryOut, StatsOut) + ConfirmSentIn{level, invoice_numbers, note}.
deps.py : singletons Storage(init_schema au boot) -> PennylaneClient -> Ledger/BankMatch/Stats
-> Reminders ; fonctions get_*_service(). main.py : FastAPI, CORS (config.CORS_ORIGINS),
include les 4 routers, GET /api/health.
```

### Agent J — les 4 routers (`ledger`, `reminders`, `bank`, `stats`)
```
Contexte : idem. Démarre APRÈS le commit de l'agent I (schemas/deps prêts).

Périmètre : backend/api/routers/*.py UNIQUEMENT.

Implémente les endpoints d'ARCHITECTURE.md. Chaque endpoint : valide input, appelle UN service
via Depends(get_*_service), sérialise via schemas. ZÉRO logique métier.
bank/upload : reçoit UploadFile, lit bytes, hsbc_parser.parse_hsbc(bytes, filename),
bank_match.match(txs, open_invoices), storage.save_matches, retourne les matchs.
POST reminders/{cid}/confirm : ConfirmSentIn -> reminder_service.confirm_sent. C'est le SEUL
endpoint qui écrit l'historique. GET reminders/{cid}/draft : retourne le texte, NE LOGUE RIEN.

Tests : TestClient FastAPI avec services mockés. Critère : /api/health 200, chaque endpoint répond.
```

→ Après vague 4 : `uvicorn api.main:app` démarre, `/api/health` répond. Commit.

---

## VAGUE 5 — parallèle (2 agents) — après vague 4

### Agent K — `ui/api-client` + `ui/hooks`
```
Contexte : Relance EHS, frontend React+Vite. L'API REST est définie dans ARCHITECTURE.md et
tourne sur VITE_API_BASE. Voir backend/api/schemas.py pour les formes JSON exactes.

Périmètre : ui/src/api-client/ et ui/src/hooks/ UNIQUEMENT.

types.ts : types miroir des schemas API. client.ts : fetch typé (getLedger, getReminders,
getDraft, confirmSent, getHistory, uploadBank (multipart), getMatches, getStats).
hooks : useLedger, useReminders, useBankUpload, useStats, useHistory (état + loading + erreur).
Critère : tsc sans erreur.
```

### Agent L — `ui/components` + `ui/pages` + `App.tsx`
```
Contexte : idem. Démarre après commit de l'agent K (client + hooks prêts). 
LIS le SKILL frontend-design : choisis une direction esthétique AFFIRMÉE (PAS Inter/Roboto,
PAS de dégradé violet sur blanc). Dashboard financier soigné, lisible, dense mais élégant.

Périmètre : ui/src/components/, ui/src/pages/, ui/src/App.tsx UNIQUEMENT.

Pages : Dashboard (KpiCard + AgingBar + top retardataires), Ledger (CustomerTable + sélection
-> CustomerDetail avec InvoiceList + DraftPanel), History.
DraftPanel : affiche le brouillon (généré via getDraft, n'écrit rien) + bouton
"J'ai envoyé cette relance" -> confirmSent -> toast + refresh historique.
PaymentBadge "Payé (banque)" sur les clients blocked_by_payment (sortis de la liste à relancer).
BankUploadDrop : dépôt de fichier HSBC (xlsx/pdf) -> uploadBank -> affiche les matchs.
Critère : npm run build OK, navigation fonctionnelle contre l'API locale.
```

→ Fin. `npm run dev` + backend lancé = dashboard fonctionnel.

---

## Récap des vagues
```
V1 (4 //)  : storage · pennylane · hsbc_parser · drafts
V2 (3 //)  : ledger · bank_match · stats
V3 (1)     : reminders (orchestrateur)
V4 (2 seq) : api socle (schemas/deps/main) → routers
V5 (2 seq) : api-client+hooks → components+pages
```
