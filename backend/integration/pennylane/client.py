"""Wrapper REST Pennylane v2, LECTURE SEULE. Seul module qui parle à Pennylane.
Traduit le JSON Pennylane en objets core. Aucun push (create/update/delete).

Auth : header ``Authorization: Bearer <PENNYLANE_TOKEN>``.
Pagination cursor : toutes les listes renvoient ``{"items": [...], "has_more": bool,
"next_cursor": "..."}`` ; on passe ``?cursor=<next_cursor>`` tant que ``has_more`` est vrai.

Source du poste client (créances)
---------------------------------
Le VRAI encours client ne vit pas dans ``/customer_invoices`` (qui ne voit qu'une
poignée de factures, souvent à ``customer: null``) mais dans les ÉCRITURES
COMPTABLES sur les comptes auxiliaires 411XXX (saisies par la comptable, reprise
SAP comprise). ``list_open_invoices`` lit donc le grand livre :
- ``/ledger_accounts`` : comptes auxiliaires clients (``type == "customer"``,
  ``number`` commençant par "411").
- ``/ledger_entry_lines`` : TOUTES les lignes d'écriture de ces comptes sur une
  fenêtre glissante (depuis le 1er janvier de l'année N-offset). L'encours ne
  dépend PLUS du lettrage (la comptable ne lettre pas au fil de l'eau les gros
  comptes anciens) : on rapproche débit/crédit nous-mêmes, en FIFO par compte.
  La fenêtre inclut déjà les reports « A-Nouveau » (posés au 1er janvier, débit
  ET crédit), donc le solde d'ouverture : inutile de remonter avant.

Noms de champs vérifiés sur l'API v2 :
- ledger_accounts : id, number, label, type, enabled, letterable.
  (filtre ``start_with`` sur ``number`` ; tri accepté = ``id`` UNIQUEMENT).
- ledger_entry_lines : id, label, debit (str), credit (str), date,
  ledger_account {id, number}, ledger_entry {id},
  lettered_ledger_entry_lines {ids: [...], url}.
- customer_invoices : id, invoice_number, label, amount, remaining_amount_with_tax,
  currency, paid, draft, date, deadline, customer ({id, url} ou null).
- customers : id, name, emails (liste).
- transactions : id, date, label, amount (signé, string), currency.
  (le tri n'accepte que ``id``).

Le filtre ``since`` utilise le format de filtre brut v2 :
``filter=[{"field": "date", "operator": "gteq", "value": "YYYY-MM-DD"}]``.
"""
from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterator

import httpx

import config
from core import reconcile
from core.models import BankTransaction, Customer, Invoice

logger = logging.getLogger(__name__)

# Page maximale autorisée par l'API v2.
_PAGE_LIMIT = 100
# Nombre maximal de tentatives sur un GET (gestion du rate limit 429).
_MAX_RETRIES = 5
# Pause entre deux pages pour ménager le rate limit (secondes).
_PAGE_PAUSE = 0.2

# Journal de banque HSBC = BQ1 (type "finances", label "Journal de trésorerie
# - EHS"). C'est le SEUL journal de banque dans le périmètre v1 ; les journaux
# Revolut (BQ2..BQ6) en sont exclus. Sa dernière écriture donne la « frontière
# comptable » : jusqu'à cette date le lettrage 411 est fiable (les paiements y
# sont déjà reflétés), au-delà on s'appuie sur l'upload HSBC manuel.
HSBC_BANK_JOURNAL_ID = 6716577

# Comptes auxiliaires clients : préfixe de numéro (411XXX).
_CUSTOMER_ACCOUNT_PREFIX = "411"
# Comptes génériques « Clients » sans tiers rattaché : à exclure de l'encours.
# 41106 = compte générique « Clients - Numéros standards » (à ne pas confondre
# avec les comptes auxiliaires 41106xxx e-commerce, écartés via type reserved).
_GENERIC_CUSTOMER_ACCOUNTS = {"411", "41102", "4111", "4117", "41106"}
# Délai d'échéance par défaut, conditions "30_days" (on n'appelle pas /customers).
_DEFAULT_PAYMENT_TERM_DAYS = 30

# Marqueur des reports à nouveau : Pennylane pose le solde d'ouverture de
# l'exercice comme une écriture datée du 1er janvier dont le libellé PEUT
# contenir « A-Nouveau ». Ces lignes servent au calcul du solde et à l'imputation
# FIFO mais ne sont pas des factures à relancer. Le rapprochement (anti-doublon
# A-Nouveau, annulations, FIFO) est délégué à ``core.reconcile``.
_OPENING_BALANCE_MARKER = "a-nouveau"
# Type d'API des journaux d'« à-nouveaux ». ATTENTION : les reports d'ouverture
# saisis par Pennylane dans ce journal portent un libellé qui reprend la facture
# d'origine (« 2025-11-05 – Factures clients - 411XXX »), SANS le mot
# « A-Nouveau ». Se fier au seul libellé laissait passer ces reports, qui
# doublonnaient alors les factures déjà présentes dans la fenêtre (double
# comptage). On identifie donc un report par son JOURNAL (ce type), le libellé
# ne servant plus que de filet de sécurité.
_CARRYOVER_JOURNAL_TYPE = "carryover"


def _normalize_name(text: Any) -> str:
    """Forme comparable d'un nom : minuscule, sans accents ni séparateurs.

    Ne garde que ``[a-z0-9]`` (espaces, tirets et accents neutralisés) pour que
    « MySignalisation Prozon » et « MY SIGNALISATION PROZON » se comparent égaux.
    """
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", stripped.lower())


class PennylaneClient:
    """Client HTTP en lecture seule pour l'API REST Pennylane v2.

    Aucune méthode n'émet de POST/PUT/DELETE : ce module ne fait que lire.
    Un ``httpx.Client`` peut être injecté (tests : transport mock) ; sinon il est
    construit à partir du token et de l'URL de base.
    """

    def __init__(self, token: str | None = None,
                 base_url: str | None = None, *,
                 client: httpx.Client | None = None,
                 timeout: float = 30.0) -> None:
        self._token = token if token is not None else config.PENNYLANE_TOKEN
        self._base_url = (base_url or config.PENNYLANE_BASE_URL).rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            },
            timeout=timeout,
        )
        # Cache id client -> nom (les factures ne portent pas le nom du client,
        # seulement {id, url} -> on joint avec /customers).
        self._customer_names: dict[int, str] = {}
        # Cache id compte auxiliaire 411XXX -> libellé du compte (= nom du tiers),
        # alimenté par ``list_customer_ledger_accounts``.
        self._ledger_account_names: dict[int, str] = {}
        # Cache des ids de journaux d'à-nouveaux (type "carryover"), résolus une
        # seule fois via ``/journals`` (None tant que non chargé).
        self._carryover_journal_ids: set[int] | None = None

    # ------------------------------------------------------------------ #
    # Cycle de vie
    # ------------------------------------------------------------------ #
    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "PennylaneClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Bas niveau : GET + pagination cursor (LECTURE SEULE)
    # ------------------------------------------------------------------ #
    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET avec retry/backoff exponentiel sur le rate limit 429.

        Jusqu'à ``_MAX_RETRIES`` tentatives. Sur un 429, on respecte l'en-tête
        ``Retry-After`` (en secondes) si présent, sinon on attend
        ``2 ** tentative`` secondes. Après épuisement, l'erreur est levée
        comme pour tout autre statut.
        """
        for attempt in range(_MAX_RETRIES):
            resp = self._client.get(path, params=params)
            if resp.status_code == 429 and attempt < _MAX_RETRIES - 1:
                retry_after = resp.headers.get("Retry-After")
                try:
                    delay = (float(retry_after) if retry_after is not None
                             else 2 ** attempt)
                except (TypeError, ValueError):
                    delay = 2 ** attempt
                time.sleep(delay)
                continue
            resp.raise_for_status()
            return resp.json()
        # Épuisement des tentatives : on lève l'erreur du dernier 429.
        resp.raise_for_status()
        return resp.json()

    def _paginate(self, path: str,
                  params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        """Itère sur TOUS les ``items`` de toutes les pages (cursor/has_more)."""
        query: dict[str, Any] = {"limit": _PAGE_LIMIT}
        if params:
            query.update(params)
        while True:
            payload = self._get(path, params=query)
            for item in payload.get("items", []):
                yield item
            if not payload.get("has_more"):
                break
            cursor = payload.get("next_cursor")
            if not cursor:
                break
            # Pause entre deux pages pour ménager le rate limit.
            time.sleep(_PAGE_PAUSE)
            query = dict(query, cursor=cursor)

    @staticmethod
    def _since_filter(since: date | None) -> dict[str, Any] | None:
        if since is None:
            return None
        return {"filter": json.dumps(
            [{"field": "date", "operator": "gteq", "value": since.isoformat()}])}

    @staticmethod
    def _receivable_window_start(today: date | None = None) -> date:
        """Date de départ de la fenêtre de rapprochement débit/crédit.

        1er janvier de (année courante − ``RECEIVABLE_WINDOW_START_YEAR_OFFSET``).
        Cette fenêtre englobe déjà les reports « A-Nouveau » de l'exercice (posés
        au 1er janvier), donc le solde d'ouverture : inutile de remonter avant.
        """
        ref = today or date.today()
        return date(ref.year - config.RECEIVABLE_WINDOW_START_YEAR_OFFSET, 1, 1)

    @staticmethod
    def _is_opening_balance(label: Any) -> bool:
        """Vrai si la ligne est un report à nouveau (libellé « A-Nouveau »)."""
        return _OPENING_BALANCE_MARKER in str(label or "").lower()

    @staticmethod
    def _number_from_line_label(label: Any) -> str | None:
        """Numéro de facture extrait du libellé d'une ligne d'écriture.

        Les libellés se terminent souvent par « … – 240343 » (tiret cadratin ou
        demi-cadratin, ou simple trait d'union). On rend la dernière séquence de
        chiffres en fin de libellé, sinon ``None``.
        """
        text = str(label or "").strip()
        match = re.search(r"(\d+)\s*$", text)
        return match.group(1) if match else None

    # ------------------------------------------------------------------ #
    # Helpers de conversion JSON -> core
    # ------------------------------------------------------------------ #
    @staticmethod
    def _decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal("0")
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal("0")

    @staticmethod
    def _date(value: Any) -> date | None:
        if not value:
            return None
        return date.fromisoformat(str(value)[:10])

    @staticmethod
    def _clean_label(label: Any) -> str:
        """Libellé d'une ligne d'écriture, espaces de bord retirés (sinon "")."""
        if not label:
            return ""
        return str(label).strip()

    def _map_customer(self, raw: dict[str, Any]) -> Customer:
        emails = raw.get("emails") or []
        email = emails[0] if emails else None
        return Customer(id=raw["id"], name=raw.get("name") or "", email=email)

    @staticmethod
    def _name_from_label(label: Any, number: Any) -> str:
        """Extrait le nom client du libellé d'une facture, quand l'objet
        ``customer`` est ``null``.

        Format observé : « Facture <NOM> - <numero> » (libellé généré). On prend
        ce qui se trouve entre « Facture » et « - <numero> ». Si rien
        d'exploitable, rend une chaîne vide.
        """
        if not label:
            return ""
        text = str(label).strip()
        # Retire le préfixe « Facture » (insensible à la casse).
        prefix = re.match(r"(?i)^facture\b\s*", text)
        if prefix:
            text = text[prefix.end():]
        # Retire le suffixe « - <numero> » (n° exact si connu, sinon - <chiffres>).
        if number:
            text = re.sub(rf"\s*-\s*{re.escape(str(number))}\s*$", "", text)
        text = re.sub(r"\s*-\s*\d+\s*$", "", text)
        return text.strip()

    def _map_invoice(self, raw: dict[str, Any], names: dict[int, str]) -> Invoice:
        customer = raw.get("customer") or {}
        customer_id = customer.get("id") or 0

        # Résolution du nom : 1) index /customers via customer.id ;
        # 2) extraction depuis le libellé (factures à customer null) ;
        # 3) « Client inconnu » (id 0) en dernier recours — JAMAIS écarter.
        customer_name = names.get(customer_id, "") if customer_id else ""
        if not customer_name:
            customer_name = self._name_from_label(
                raw.get("label"), raw.get("invoice_number"))
        if not customer_name:
            customer_name = "Client inconnu"
            customer_id = 0

        # remaining_amount : fourni par l'API (TTC) ; sinon amount si non payé.
        if raw.get("remaining_amount_with_tax") is not None:
            remaining = self._decimal(raw["remaining_amount_with_tax"])
        elif not raw.get("paid"):
            remaining = self._decimal(raw.get("amount"))
        else:
            remaining = Decimal("0")

        return Invoice(
            id=raw["id"],
            number=raw.get("invoice_number") or raw.get("label") or str(raw["id"]),
            customer_id=customer_id,
            customer_name=customer_name,
            date=self._date(raw.get("date")) or date.min,
            due_date=self._date(raw.get("deadline")),
            amount=self._decimal(raw.get("amount")),
            currency=raw.get("currency") or "EUR",
            paid=bool(raw.get("paid")),
            remaining_amount=remaining,
        )

    def _map_transaction(self, raw: dict[str, Any]) -> BankTransaction:
        amount = self._decimal(raw.get("amount"))
        credit = amount if amount > 0 else None
        debit = -amount if amount < 0 else None
        tx_date = self._date(raw.get("date"))
        return BankTransaction(
            ref=str(raw["id"]),
            value_date=tx_date or date.min,
            op_date=tx_date,
            label=raw.get("label") or "",
            client_ref=None,
            credit=credit,
            debit=debit,
            source="revolut",
        )

    # ------------------------------------------------------------------ #
    # API publique
    # ------------------------------------------------------------------ #
    def list_customers(self) -> list[Customer]:
        """Tous les clients (pagine tout). Met aussi à jour le cache des noms."""
        customers = [self._map_customer(raw)
                     for raw in self._paginate("/customers")]
        for c in customers:
            self._customer_names[c.id] = c.name
        return customers

    def list_all_invoices(self, since: date | None = None) -> list[Invoice]:
        """Toutes les factures clients (pagine tout), enrichies du nom client."""
        names = self._customer_names_map()
        return [self._map_invoice(raw, names)
                for raw in self._paginate("/customer_invoices",
                                          self._since_filter(since))]

    def list_customer_ledger_accounts(self) -> dict[int, str]:
        """Comptes auxiliaires clients (411XXX) : ``{ledger_account_id: nom}``.

        Source réelle du poste client. On filtre côté API sur ``number``
        commençant par "411", puis on ne garde que les comptes
        ``type == "customer"`` et ``enabled`` : on écarte les comptes
        ``reserved`` (41106xxx e-commerce), les comptes désactivés
        (``enabled == False``) et les comptes génériques au libellé « Clients »
        (411, 41102, 4111, 4117, 41106) qui ne portent aucun tiers. On écarte
        aussi les clients listés dans ``config.EXCLUDED_CUSTOMER_NAMES`` (bons
        payeurs à gros volume) : leurs lignes ne sont jamais récupérées. Pagine
        tout.

        Le résultat est mis en cache sur l'instance (``_ledger_account_names``)
        pour servir de jointure id -> nom aux lignes d'écriture.
        """
        params = {
            "filter": json.dumps([{"field": "number", "operator": "start_with",
                                   "value": _CUSTOMER_ACCOUNT_PREFIX}]),
            "sort": "id",  # le tri n'accepte que ``id`` (sinon 400).
        }
        # Fragments de noms à exclure (bons payeurs à gros volume), normalisés une
        # seule fois. Un compte est écarté si l'un des fragments est contenu dans
        # son libellé normalisé : ses lignes ne seront jamais paginées (gain de
        # vitesse) et il sort des relances / encours / stats.
        excluded = [n for n in (_normalize_name(name)
                                for name in config.EXCLUDED_CUSTOMER_NAMES) if n]
        # Numéros de compte exclus par correspondance EXACTE (casse/espaces
        # ignorés) : cible un compte précis sans écarter ses voisins homonymes.
        excluded_numbers = {n.strip().upper()
                            for n in config.EXCLUDED_CUSTOMER_ACCOUNT_NUMBERS
                            if n.strip()}
        accounts: dict[int, str] = {}
        for raw in self._paginate("/ledger_accounts", params):
            if raw.get("type") != "customer":
                continue
            if raw.get("enabled") is False:
                continue  # compte désactivé -> hors encours
            number = str(raw.get("number") or "")
            if number in _GENERIC_CUSTOMER_ACCOUNTS:
                continue
            if number.upper() in excluded_numbers:
                logger.info("Compte client exclu du poste (numéro) : %s", number)
                continue
            label = raw.get("label") or number
            norm_label = _normalize_name(label)
            if any(fragment in norm_label for fragment in excluded):
                logger.info("Compte client exclu du poste : %s (%s)",
                            label, number)
                continue
            accounts[raw["id"]] = label
        self._ledger_account_names = accounts
        return accounts

    def list_open_receivable_lines(self) -> list[dict[str, Any]]:
        """TOUTES les lignes d'écriture des comptes clients sur la fenêtre.

        Pour CHAQUE compte client 411XXX, pagine ``/ledger_entry_lines`` filtré
        sur ce compte ET sur ``date >= window_start`` (1er janvier de l'année
        N-offset), trié par date croissante. On NE filtre PLUS sur le lettrage :
        on récupère tout (débits ET crédits, reports « A-Nouveau » inclus), car
        le rapprochement débit/crédit est fait nous-mêmes (FIFO) en aval. Les
        gros comptes anciens ne sont pas lettrés au fil de l'eau : se fier au
        lettrage faussait l'encours (crédits ignorés).
        """
        accounts = self.list_customer_ledger_accounts()
        window_start = self._receivable_window_start()
        lines: list[dict[str, Any]] = []
        for account_id in accounts:
            params = {
                "filter": json.dumps([
                    {"field": "ledger_account_id", "operator": "eq",
                     "value": account_id},
                    {"field": "date", "operator": "gteq",
                     "value": window_start.isoformat()},
                ]),
                "sort": "date",  # plus ancienne d'abord (ordre FIFO).
            }
            lines.extend(self._paginate("/ledger_entry_lines", params))
        return lines

    def list_open_invoices(self) -> list[Invoice]:
        """Encours client réel, par rapprochement débit/crédit via core.reconcile.

        Lit le poste client dans les écritures comptables (comptes 411XXX) et non
        dans ``/customer_invoices``, et NE dépend plus du lettrage (la comptable
        ne lettre pas au fil de l'eau les gros comptes anciens). Pour chaque
        compte 411, on construit les lignes brutes normalisées
        (``core.reconcile.RawLine``) et on délègue le rapprochement à
        ``core.reconcile.reconcile_account``, qui :

        - neutralise les annulations (facture + contre-passation de même date et
          montant) ;
        - exclut les reports « A-Nouveau » qui ne font que recopier des factures
          DÉJÀ présentes dans la fenêtre (anti double-comptage du solde
          d'ouverture), tout en conservant les A-Nouveau légitimes (créance
          réellement antérieure à la fenêtre) ;
        - impute en FIFO le total des crédits sur les débits restants.

        Chaque créance résiduelle (``OpenItem``) devient une ``Invoice``. Si le
        compte est soldé, ``reconcile_account`` rend ``[]`` et aucune ``Invoice``
        n'est émise pour ce client.
        """
        lines = self.list_open_receivable_lines()
        names = self._ledger_account_names
        window_start = self._receivable_window_start()

        # Regroupe les lignes par compte (l'ordre n'importe pas : reconcile_account
        # re-trie), pour un rapprochement compte par compte.
        by_account: dict[int, list[dict[str, Any]]] = {}
        for raw in lines:
            account = raw.get("ledger_account") or {}
            account_id = account.get("id") or 0
            by_account.setdefault(account_id, []).append(raw)

        carryover = self._get_carryover_journal_ids()
        out: list[Invoice] = []
        for account_id, account_lines in by_account.items():
            raw_lines = [self._raw_reconcile_line(raw, carryover)
                         for raw in account_lines]
            customer_name = names.get(account_id, "")
            for item in reconcile.reconcile_account(raw_lines, window_start):
                out.append(self._open_item_to_invoice(
                    item, account_id, customer_name))
        return out

    def _get_carryover_journal_ids(self) -> set[int]:
        """Ids des journaux d'à-nouveaux (type « carryover »), mis en cache.

        Une seule requête ``/journals`` par instance. Les reports d'ouverture y
        sont saisis sans toujours porter « A-Nouveau » dans leur libellé : c'est
        le journal qui les identifie de façon fiable (cf. ``_CARRYOVER_JOURNAL_TYPE``).
        """
        if self._carryover_journal_ids is None:
            self._carryover_journal_ids = {
                raw["id"] for raw in self._paginate("/journals")
                if raw.get("type") == _CARRYOVER_JOURNAL_TYPE
            }
        return self._carryover_journal_ids

    def _raw_reconcile_line(self, raw: dict[str, Any],
                            carryover_journal_ids: set[int]) -> reconcile.RawLine:
        """Traduit une ligne d'écriture brute Pennylane en ``reconcile.RawLine``.

        Une ligne est un report d'ouverture (« A-Nouveau ») si elle provient d'un
        journal d'à-nouveaux (type « carryover ») OU si son libellé porte le
        marqueur « A-Nouveau » (filet de sécurité). Repérer le report par son
        seul libellé laissait passer les A-Nouveau dont Pennylane recopie le
        libellé de la facture d'origine : ils doublonnaient l'encours.
        """
        journal = raw.get("journal") or {}
        is_opening = (journal.get("id") in carryover_journal_ids
                      or self._is_opening_balance(raw.get("label")))
        return reconcile.RawLine(
            id=raw["id"],
            date=self._date(raw.get("date")),
            debit=self._decimal(raw.get("debit")),
            credit=self._decimal(raw.get("credit")),
            label=raw.get("label") or "",
            is_opening_balance=is_opening,
            invoice_number=self._number_from_line_label(raw.get("label")),
        )

    def _open_item_to_invoice(self, item: reconcile.OpenItem, account_id: int,
                              customer_name: str) -> Invoice:
        """Convertit une créance résiduelle (``OpenItem``) en ``Invoice``.

        À défaut de numéro de facture exploitable, on affiche la DATE de la ligne
        (« Facture du JJ/MM/AAAA ») : le grand livre n'a pas de numéro fiable et
        l'id technique n'a aucun sens à l'écran. L'``id`` reste l'id de la ligne.
        """
        number = item.invoice_number or f"Facture du {item.date:%d/%m/%Y}"
        return Invoice(
            id=item.source_line_id,
            number=number,
            customer_id=account_id,
            customer_name=customer_name,
            date=item.date,
            due_date=item.date + timedelta(days=_DEFAULT_PAYMENT_TERM_DAYS),
            amount=item.amount_original,
            currency="EUR",
            paid=False,
            remaining_amount=item.amount_remaining,
        )

    def hsbc_accounting_boundary(self) -> date | None:
        """Frontière comptable HSBC : date de la dernière écriture du journal BQ1.

        Lit l'écriture la plus récente du journal de banque HSBC
        (``HSBC_BANK_JOURNAL_ID``) via ``/ledger_entries`` trié par date
        décroissante, limité à 1, et retourne sa date. Rend ``None`` si le
        journal ne contient aucune écriture.

        Jusqu'à cette date (incluse), les paiements clients sont déjà reflétés
        dans l'encours (lignes 411 lettrées, donc absentes) : seuls les
        rapprochements HSBC manuels POSTÉRIEURS servent encore au blocage des
        relances.
        """
        params = {
            "filter": json.dumps(
                [{"field": "journal_id", "operator": "eq",
                  "value": HSBC_BANK_JOURNAL_ID}]),
            "sort": "-date",
            "limit": 1,
        }
        payload = self._get("/ledger_entries", params)
        items = payload.get("items") or []
        if not items:
            return None
        return self._date(items[0].get("date"))

    def get_invoice(self, invoice_id: int) -> Invoice:
        raw = self._get(f"/customer_invoices/{invoice_id}")
        customer = raw.get("customer") or {}
        customer_id = customer.get("id") or 0
        names = dict(self._customer_names)
        if customer_id and customer_id not in names:
            names[customer_id] = self._fetch_customer_name(customer_id)
        return self._map_invoice(raw, names)

    def list_bank_transactions(self, since: date | None = None) -> list[BankTransaction]:
        """Transactions des comptes liés à Pennylane (Revolut). source='revolut'.

        Par défaut, ne récupère que les transactions des
        ``config.REMINDER_LOOKBACK_DAYS`` derniers jours (90 par défaut), via le
        filtre ``date gteq`` de l'API (le tri n'étant accepté que sur ``id``).
        """
        if since is None:
            since = date.today() - timedelta(days=config.REMINDER_LOOKBACK_DAYS)
        return [self._map_transaction(raw)
                for raw in self._paginate("/transactions", self._since_filter(since))]

    # ------------------------------------------------------------------ #
    # Internes : résolution des noms de client
    # ------------------------------------------------------------------ #
    def _customer_names_map(self) -> dict[int, str]:
        """Map id -> nom, construite via /customers (mise en cache sur l'instance)."""
        if not self._customer_names:
            self.list_customers()
        return self._customer_names

    def _fetch_customer_name(self, customer_id: int) -> str:
        try:
            raw = self._get(f"/customers/{customer_id}")
        except httpx.HTTPError:
            return ""
        name = raw.get("name") or ""
        self._customer_names[customer_id] = name
        return name
