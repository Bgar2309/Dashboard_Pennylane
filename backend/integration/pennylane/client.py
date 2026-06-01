"""Wrapper REST Pennylane v2, LECTURE SEULE. Seul module qui parle à Pennylane.
Traduit le JSON Pennylane en objets core. Aucun push (create/update/delete).

Auth : header ``Authorization: Bearer <PENNYLANE_TOKEN>``.
Pagination cursor : toutes les listes renvoient ``{"items": [...], "has_more": bool,
"next_cursor": "..."}`` ; on passe ``?cursor=<next_cursor>`` tant que ``has_more`` est vrai.

Noms de champs vérifiés sur l'API v2 (endpoints /customer_invoices, /customers,
/transactions) :
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
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterator

import httpx

import config
from core.models import BankTransaction, Customer, Invoice

# Page maximale autorisée par l'API v2.
_PAGE_LIMIT = 100


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
        resp = self._client.get(path, params=params)
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
            query = dict(query, cursor=cursor)

    @staticmethod
    def _since_filter(since: date | None) -> dict[str, Any] | None:
        if since is None:
            return None
        return {"filter": json.dumps(
            [{"field": "date", "operator": "gteq", "value": since.isoformat()}])}

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

    def _map_customer(self, raw: dict[str, Any]) -> Customer:
        emails = raw.get("emails") or []
        email = emails[0] if emails else None
        return Customer(id=raw["id"], name=raw.get("name") or "", email=email)

    def _map_invoice(self, raw: dict[str, Any], names: dict[int, str]) -> Invoice:
        customer = raw.get("customer") or {}
        customer_id = customer.get("id") or 0

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
            customer_name=names.get(customer_id, ""),
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

    def list_open_invoices(self) -> list[Invoice]:
        """Factures clients non soldées (remaining_amount > 0). Pagine tout.

        On exclut les brouillons (``draft``) : ce ne sont pas des créances réelles.
        """
        names = self._customer_names_map()
        out: list[Invoice] = []
        for raw in self._paginate("/customer_invoices"):
            if raw.get("draft"):
                continue
            inv = self._map_invoice(raw, names)
            if inv.remaining_amount > 0:
                out.append(inv)
        return out

    def get_invoice(self, invoice_id: int) -> Invoice:
        raw = self._get(f"/customer_invoices/{invoice_id}")
        customer = raw.get("customer") or {}
        customer_id = customer.get("id") or 0
        names = dict(self._customer_names)
        if customer_id and customer_id not in names:
            names[customer_id] = self._fetch_customer_name(customer_id)
        return self._map_invoice(raw, names)

    def list_bank_transactions(self, since: date | None = None) -> list[BankTransaction]:
        """Transactions des comptes liés à Pennylane (Revolut). source='revolut'."""
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
