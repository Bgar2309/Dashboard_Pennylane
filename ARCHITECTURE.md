# Architecture — Relance EHS

Dashboard de relance client basé sur Pennylane (vérité comptable, lecture seule)
+ rapprochement bancaire HSBC local pour ne jamais relancer un client déjà payé.

Stack : FastAPI (Python 3.12) · React + Vite · SQLite (volume Railway `/data`) · Railway (2 services).
Pennylane = API REST v2 directe (token de service dédié, scopes readonly). Aucun push vers Pennylane.

---

## Diagramme de dépendances

```
┌──────────────────────────────────────────────────────────────┐
│  UI  (React + Vite)                                            │
│  ui/api-client · ui/hooks · ui/components · ui/pages           │
└───────────────────────────────┬──────────────────────────────┘
                                 │ HTTP (REST)
┌───────────────────────────────▼──────────────────────────────┐
│  API  (FastAPI)                                                │
│  routers: ledger · reminders · bank · stats                    │
└───┬───────────────┬───────────────┬───────────────────┬───────┘
    │               │               │                   │
┌───▼──────┐ ┌──────▼───────┐ ┌─────▼────────┐ ┌─────────▼───────┐
│ service/ │ │  service/    │ │  service/    │ │   service/      │
│ ledger   │ │  reminders   │ │  bank_match  │ │   stats         │
└───┬──────┘ └──┬────────┬──┘ └────┬─────┬───┘ └──┬──────────────┘
    │           │        │         │     │        │
    │      ┌────▼───┐    │    ┌────▼─┐   │   (lit ledger + bank)
    │      │ drafts │    │    │ hsbc │   │
    │      │(textes)│    │    │parser│   │
    │      └────────┘    │    └──────┘   │
    │                    │               │
┌───▼────────────────────▼───────────────▼──────────────────────┐
│  integration/pennylane   (REST v2, readonly)                   │
└────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│  storage  (SQLite : reminders_log, payment_matches, cache)      │
└────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│  core  (modèles partagés : Invoice, Customer, BankTx, Match…)   │
└────────────────────────────────────────────────────────────────┘
```

Règle d'or : les dépendances vont du haut vers le bas. `core` et `storage` ne connaissent
personne. `integration` ne connaît que `core`. Les `service` ne dépendent jamais entre eux
(sauf `stats` qui lit des données déjà produites, jamais d'autres services en direct — il
relit `storage` et appelle `service/ledger`).

---

## Modèles partagés — `core`

Module sans dépendances. Tous les autres l'importent en lecture seule.

```python
# core/models.py
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

class ReminderLevel(str, Enum):
    NONE = "none"           # pas encore en retard
    FIRST = "first"         # 1ère relance (douce)
    SECOND = "second"       # 2ème relance (ferme)
    FORMAL = "formal"       # mise en demeure

class AgingBucket(str, Enum):
    NOT_DUE = "not_due"
    D0_30 = "0-30"
    D30_60 = "30-60"
    D60_90 = "60-90"
    D90_PLUS = "90+"

class MatchConfidence(str, Enum):
    STRONG = "strong"   # n° facture 26xxxx trouvé + montant ≈
    MEDIUM = "medium"   # nom client fuzzy + montant exact
    WEAK   = "weak"     # montant exact seul, fenêtre de date
    NONE   = "none"

@dataclass
class Customer:
    id: int                      # id Pennylane
    name: str
    email: str | None = None

@dataclass
class Invoice:
    id: int                      # id Pennylane
    number: str                  # ex "CA 2610144" / "260604"
    customer_id: int
    customer_name: str
    date: date                   # date de facture
    due_date: date | None
    amount: Decimal              # TTC
    currency: str
    paid: bool                   # statut Pennylane (lettré)
    remaining_amount: Decimal    # reste dû (gère paiements partiels)

@dataclass
class BankTransaction:
    ref: str                     # Référence bancaire HSBC
    value_date: date             # Date de valeur
    op_date: date | None         # Date opération
    label: str                   # Libellé complet (champ riche)
    client_ref: str | None       # Référence client (colonne HSBC)
    credit: Decimal | None       # Montant du crédit (None si débit)
    debit: Decimal | None
    source: str = "hsbc"         # "hsbc" | "revolut" (revolut via pennylane)

@dataclass
class PaymentMatch:
    bank_ref: str
    invoice_id: int | None
    invoice_number: str | None
    customer_name: str | None
    amount: Decimal
    confidence: MatchConfidence
    matched_invoice_numbers: list[str] = field(default_factory=list)
    reason: str = ""             # explication lisible du match

@dataclass
class ReminderLogEntry:
    id: int
    customer_id: int
    customer_name: str
    level: ReminderLevel
    sent_at: datetime
    invoice_numbers: list[str]
    note: str | None = None

@dataclass
class CustomerDunningRow:
    """Une ligne du grand livre client agrégée pour la vue relance."""
    customer: Customer
    open_invoices: list[Invoice]
    total_due: Decimal
    oldest_due_date: date | None
    worst_bucket: AgingBucket
    suggested_level: ReminderLevel
    last_reminder: ReminderLogEntry | None
    blocked_by_payment: bool       # True si un match HSBC couvre le solde → ne pas relancer
```

**Ne fait PAS** : aucune logique, aucun I/O. Juste des dataclasses + enums + helpers purs
(`bucket_for(due_date, today)`, `level_for(bucket, last_reminder)`).

**Dépend de** : rien.

---

## Module : `storage`

**Rôle** : Persistance SQLite. Historique des relances, matchs de paiement validés, cache
optionnel des factures Pennylane (pour ne pas retaper l'API à chaque rafraîchissement).

**Interface publique** (Python) :
```python
# storage/db.py
class Storage:
    def __init__(self, db_path: str): ...   # défaut: env DATABASE_PATH ou /data/relance.db
    def init_schema(self) -> None: ...

    # --- Historique des relances (loggé UNIQUEMENT sur confirmation "J'ai envoyé") ---
    def log_reminder(self, customer_id: int, customer_name: str,
                     level: ReminderLevel, invoice_numbers: list[str],
                     note: str | None = None) -> ReminderLogEntry: ...
    def get_last_reminder(self, customer_id: int) -> ReminderLogEntry | None: ...
    def list_reminders(self, customer_id: int | None = None,
                       limit: int = 100) -> list[ReminderLogEntry]: ...

    # --- Matchs de paiement HSBC (cache des rapprochements calculés/validés) ---
    def save_matches(self, matches: list[PaymentMatch]) -> None: ...
    def list_matches(self, since: date | None = None) -> list[PaymentMatch]: ...
    def clear_matches(self) -> None: ...

    # --- Cache factures (optionnel, TTL géré par le service) ---
    def cache_invoices(self, invoices: list[Invoice]) -> None: ...
    def get_cached_invoices(self) -> list[Invoice]: ...
    def cache_age_seconds(self) -> float | None: ...
```

Schéma SQLite (tables) : `reminders_log`, `payment_matches`, `invoice_cache`, `cache_meta`.

**Ne fait PAS** : aucune logique métier (pas de calcul d'aging, pas de matching). Pas
d'appel réseau. Stocke et rend, point.

**Dépend de** : `core` (types), variable d'env `DATABASE_PATH`.

---

## Module : `integration/pennylane`

**Rôle** : Wrapper unique sur l'API REST Pennylane v2. Traduit le JSON Pennylane en
objets `core`. SEUL endroit du code qui parle à Pennylane. Lecture seule.

**Interface publique** (Python) :
```python
# integration/pennylane/client.py
class PennylaneClient:
    def __init__(self, token: str, base_url: str = "https://app.pennylane.com/api/external/v2"): ...

    def list_customers(self) -> list[Customer]: ...
    def list_open_invoices(self) -> list[Invoice]:
        """Factures clients NON soldées (remaining_amount > 0). Gère la pagination."""
    def list_all_invoices(self, since: date | None = None) -> list[Invoice]: ...
    def get_invoice(self, invoice_id: int) -> Invoice: ...
    def list_bank_transactions(self, since: date | None = None) -> list[BankTransaction]:
        """Transactions des comptes liés à Pennylane (Revolut). source='revolut'."""
```

Notes d'implémentation :
- Auth : header `Authorization: Bearer <token>`. Token = env `PENNYLANE_TOKEN`.
- Scopes requis : `customer_invoices:readonly`, `transactions:readonly`, `customers:readonly`.
- Pagination cursor (`?cursor=` / `has_more`) — TOUT paginer, ne jamais s'arrêter à la page 1.
- `remaining_amount` : si l'API le fournit l'utiliser tel quel ; sinon `amount` si `paid=false`.
- Endpoints v2 : `/customer_invoices`, `/customers`, `/transactions`. Vérifier les noms
  exacts de champs sur https://pennylane.readme.io/reference (le dev de ce module DOIT lire
  la doc avant de coder — ne pas deviner les champs).

**Ne fait PAS** : aucun push (create/update/delete). Pas de matching. Pas de calcul d'aging.
Pas de persistance. Pas de MCP — REST direct uniquement.

**Dépend de** : `core`, env `PENNYLANE_TOKEN`.

---

## Module : `integration/hsbc_parser`

**Rôle** : Parser robuste des relevés HSBC (XLSX **et** PDF) → `list[BankTransaction]`.
Normalise l'encodage, ne garde que les lignes de mouvement, sépare crédit/débit.

**Interface publique** (Python) :
```python
# integration/hsbc_parser/parser.py
def parse_hsbc_xlsx(file_bytes: bytes) -> list[BankTransaction]:
    """Parse un export Excel HSBC. Colonnes attendues : Libellé, Référence client,
    Montant du crédit, Montant du débit, Date de valeur, Date opération, Référence bancaire."""

def parse_hsbc_pdf(file_bytes: bytes) -> list[BankTransaction]:
    """Parse un relevé PDF HSBC via pdfplumber (extraction de tableaux). Best-effort robuste :
    si une ligne est ambiguë, la marquer mais ne pas planter."""

def parse_hsbc(file_bytes: bytes, filename: str) -> list[BankTransaction]:
    """Dispatch selon extension (.xlsx/.xls → xlsx ; .pdf → pdf)."""
```

Règles de parsing (issues de l'analyse du fichier réel) :
- En-têtes de compte répétés sur chaque ligne (IBAN, BIC, soldes de clôture) → ignorés.
- Encodage : remplacer les `?` parasites (ex `Tesla?FR?`) — normaliser en espace.
- `Montant du crédit` rempli → `credit` ; `Montant du débit` rempli → `debit`.
- Dates au format `DD/MM/YYYY`.
- Ne PAS filtrer ici les internes/frais : le parser rend TOUT, le filtrage est métier
  (fait dans `service/bank_match`). Le parser est neutre.

**Ne fait PAS** : pas de matching, pas de filtrage métier, pas d'appel Pennylane, pas de DB.

**Dépend de** : `core`. Libs : `openpyxl`/`pandas` (xlsx), `pdfplumber` (pdf).

---

## Module : `service/ledger`

**Rôle** : Construit le grand livre client à un instant T. Récupère les factures ouvertes
Pennylane, calcule l'aging par facture et par client, agrège par client.

**Interface publique** (Python) :
```python
# service/ledger/service.py
class LedgerService:
    def __init__(self, pennylane: PennylaneClient, storage: Storage): ...

    def get_open_invoices(self, use_cache: bool = True,
                          max_cache_age_s: int = 1800) -> list[Invoice]: ...
    def aging_for(self, invoice: Invoice, today: date) -> AgingBucket: ...
    def build_dunning_rows(self, today: date) -> list[CustomerDunningRow]:
        """Agrège par client, calcule worst_bucket, total_due, suggested_level
        (sans tenir compte de la banque ni de l'historique — ça c'est reminders)."""
```

**Ne fait PAS** : pas de génération de texte, pas de matching bancaire (il fournit la base
brute ; `service/reminders` combine avec banque + historique). Pas d'appel HTTP direct.

**Dépend de** : `core`, `integration/pennylane`, `storage`.

---

## Module : `service/bank_match`

**Rôle** : Le cœur "ne jamais relancer un client déjà payé". Prend les transactions HSBC
(parsées) + Revolut (Pennylane) + les factures ouvertes, et calcule les rapprochements.

**Interface publique** (Python) :
```python
# service/bank_match/service.py
class BankMatchService:
    def __init__(self, storage: Storage): ...

    def is_client_payment(self, tx: BankTransaction) -> bool:
        """Filtre : True seulement si crédit ET pas un virement interne/frais/TVA.
        Exclut : libellés contenant EHS GROUP FRANCE (interne/treso), ARRETE DE COMPTE,
        FRAIS, TVA/FACT MENSUELLE, FACT MENSUELLE HT, FACTURES CB, COM. D'INTERVENTION,
        et tous les débits (PRLV SEPA, etc.)."""

    def extract_invoice_numbers(self, label: str) -> list[str]:
        """Détecte les n° de facture EHS au format 26xxxx / 261xxx / CA 26xxxxx dans le libellé."""

    def match(self, txs: list[BankTransaction],
              open_invoices: list[Invoice]) -> list[PaymentMatch]:
        """3 niveaux : STRONG (n° facture + montant≈), MEDIUM (nom client fuzzy + montant exact),
        WEAK (montant exact seul). Retourne un PaymentMatch par transaction client pertinente."""

    def covered_invoice_ids(self, matches: list[PaymentMatch]) -> set[int]:
        """Ids de factures considérées payées par la banche (à exclure des relances)."""
```

Constantes de filtrage exposées dans `service/bank_match/filters.py` (listes éditables :
`INTERNAL_LABELS`, `FEE_LABELS`, `INVOICE_NUMBER_REGEX`).

**Ne fait PAS** : ne parse pas les fichiers (c'est `hsbc_parser`). N'écrit pas dans Pennylane.
Ne génère pas de texte. Peut persister les matchs via `storage` (cache).

**Dépend de** : `core`, `storage`. Fuzzy matching : `rapidfuzz` (léger, pas de dépendance lourde).

---

## Module : `service/reminders`

**Rôle** : Orchestre la vue "relances à faire". Combine `ledger` (factures + aging),
`bank_match` (paiements reçus → blocage), et `storage` (historique → ne pas re-relancer trop
tôt). Détermine le niveau de relance final et délègue la génération du texte à `drafts`.

**Interface publique** (Python) :
```python
# service/reminders/service.py
class ReminderService:
    def __init__(self, ledger: LedgerService, bank_match: BankMatchService,
                 storage: Storage, drafts: DraftGenerator): ...

    def dunning_view(self, today: date,
                     hsbc_txs: list[BankTransaction] | None = None,
                     min_days_between_reminders: int = 8) -> list[CustomerDunningRow]:
        """Vue complète : aging + blocage paiement (HSBC+Revolut) + historique.
        blocked_by_payment=True si la banque couvre le solde.
        suggested_level ajusté selon last_reminder (anti-spam)."""

    def generate_draft(self, customer_id: int, today: date) -> str:
        """Retourne le TEXTE du brouillon de relance. NE LOGUE RIEN."""

    def confirm_sent(self, customer_id: int, level: ReminderLevel,
                     invoice_numbers: list[str], note: str | None = None) -> ReminderLogEntry:
        """Appelé UNIQUEMENT quand Bruno clique 'J'ai envoyé cette relance'.
        C'est la SEULE méthode qui écrit dans reminders_log."""
```

Règle critique : `generate_draft` ne crée AUCUNE trace. Seul `confirm_sent` écrit dans la DB.

**Ne fait PAS** : pas d'envoi d'email réel. Pas d'appel Pennylane direct (passe par ledger).

**Dépend de** : `core`, `service/ledger`, `service/bank_match`, `service/reminders/drafts`, `storage`.

---

## Module : `service/reminders/drafts`

**Rôle** : Génère le texte des brouillons de relance, ton adapté au niveau (FIRST douce,
SECOND ferme, FORMAL mise en demeure). Templates FR (clients EHS).

**Interface publique** (Python) :
```python
# service/reminders/drafts.py
class DraftGenerator:
    def render(self, customer: Customer, invoices: list[Invoice],
               level: ReminderLevel, today: date) -> str:
        """Texte prêt à copier-coller : objet implicite + corps + tableau des factures dues."""
```

**Ne fait PAS** : pas d'appel LLM en v1 (templates déterministes — fiables, pas de coût,
pas d'aléa). Pas de DB, pas de réseau. (Évolution possible : variante LLM via API plus tard.)

**Dépend de** : `core` uniquement.

---

## Module : `service/stats`

**Rôle** : KPIs du dashboard : encours total, DSO, retard moyen, top retardataires,
répartition par bucket d'aging, encours par client.

**Interface publique** (Python) :
```python
# service/stats/service.py
class StatsService:
    def __init__(self, ledger: LedgerService, storage: Storage): ...
    def dashboard_kpis(self, rows: list[CustomerDunningRow]) -> dict: ...
    def aging_distribution(self, rows: list[CustomerDunningRow]) -> dict[str, Decimal]: ...
    def top_overdue(self, rows: list[CustomerDunningRow], n: int = 10) -> list[dict]: ...
```

**Ne fait PAS** : pas de calcul d'aging brut (il consomme les `CustomerDunningRow` déjà
construits). Pas de réseau, pas d'écriture.

**Dépend de** : `core`, `service/ledger`, `storage`.

---

## Module : `api`

**Rôle** : Endpoints FastAPI. Validation Pydantic, appel d'UN service, sérialisation. Zéro
logique métier. Découpé en routers par domaine (parallélisable).

**Endpoints** :
```
GET  /api/ledger                 → grand livre client (CustomerDunningRow[])   [router: ledger]
GET  /api/ledger/{customer_id}   → détail factures ouvertes d'un client
GET  /api/reminders              → vue relances à faire (avec blocage banque)  [router: reminders]
GET  /api/reminders/{cid}/draft  → texte du brouillon (ne logue rien)
POST /api/reminders/{cid}/confirm→ {level, invoice_numbers, note} → log envoi  [router: reminders]
GET  /api/reminders/history      → historique des relances loggées
POST /api/bank/upload            → multipart fichier HSBC (xlsx/pdf) → matchs   [router: bank]
GET  /api/bank/matches           → derniers matchs calculés
GET  /api/stats                  → KPIs dashboard                              [router: stats]
GET  /api/health                 → ok
```

Pydantic schemas dans `api/schemas.py` (miroir des dataclasses `core`, sérialisables JSON).
Dépendances injectées via `api/deps.py` (singletons Storage, PennylaneClient, services).

**Ne fait PAS** : aucune logique métier. Pas de parsing (délègue à hsbc_parser via le service).

**Dépend de** : tous les `service/*`, `core`. (Ne dépend PAS de `integration` en direct —
sauf `bank/upload` qui appelle `hsbc_parser` puis `bank_match`.)

---

## Module : `ui`

**Rôle** : React + Vite. Dashboard visuellement soigné.

**Structure** :
```
ui/src/
├── api-client/        # client typé (fetch) — types miroir des schemas API
├── hooks/             # useLedger, useReminders, useBankUpload, useStats
├── components/        # KpiCard, AgingBar, CustomerTable, InvoiceList,
│                      #   DraftPanel (avec bouton "J'ai envoyé"), BankUploadDrop,
│                      #   PaymentBadge (blocked_by_payment), ReminderLevelTag
├── pages/             # Dashboard (KPIs + aging), Ledger (grand livre + sélection client),
│                      #   CustomerDetail (factures + brouillon + confirm), History
└── App.tsx
```

Flux UI clé : sélection d'un client → panneau détail → factures dues + brouillon affiché
→ bouton **"J'ai envoyé cette relance"** → POST confirm → toast + refresh historique.
Badge "Payé (banque)" sur les clients où `blocked_by_payment=true` → sortis de la liste à relancer.

**Ne fait PAS** : aucune logique métier (calculs côté API). Pas d'appel direct Pennylane/HSBC.

**Dépend de** : l'API (contrat REST ci-dessus). Stack UI : voir SKILL frontend-design.

---

## Ordre de construction & vagues de parallélisation

```
Vague 1 (parallèle, aucune dépendance interne) :
  - core
  - storage            (dépend de core — core est trivial, peut être stubké en 1er)
  - integration/pennylane
  - integration/hsbc_parser
  - service/reminders/drafts   (ne dépend que de core)

Vague 2 (parallèle, dépend de la vague 1) :
  - service/ledger
  - service/bank_match
  - service/stats

Vague 3 (séquencée après v2 — dépend de tous les services) :
  - service/reminders          (orchestrateur ; dépend ledger+bank_match+drafts+storage)

Vague 4 (parallèle, dépend des services) :
  - api/router_ledger
  - api/router_reminders
  - api/router_bank
  - api/router_stats
  (+ api/deps.py, api/schemas.py construits en premier dans cette vague — 1 agent dédié court)

Vague 5 (parallèle, dépend de l'API) :
  - ui/api-client + hooks
  - ui/components + pages
```

`core` est minuscule : le faire en tout premier (ou le scaffolder complet en phase 3) débloque
tout le monde. `storage`, `pennylane`, `hsbc_parser`, `drafts` n'ont alors plus de blocage.
