"""Tests du client REST Pennylane v2 (lecture seule).

Aucun appel réseau réel : on injecte un ``httpx.Client`` monté sur un
``httpx.MockTransport`` qui sert des payloads d'exemple calqués sur l'API v2
(champs exacts : items / has_more / next_cursor, invoice_number,
remaining_amount_with_tax, deadline, emails, amount signé...).
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import parse_qs

import httpx
import pytest

import config
from core.models import BankTransaction, Customer, Invoice
from integration.pennylane import PennylaneClient
from integration.pennylane import client as client_module

BASE_URL = "https://app.pennylane.com/api/external/v2"


# --------------------------------------------------------------------------- #
# Payloads d'exemple (forme réelle de l'API v2)
# --------------------------------------------------------------------------- #
CUSTOMERS_PAGES = {
    None: {
        "items": [
            {"id": 253399460, "name": "SIGNAL ET DECO", "emails": ["paie@signal.fr"]},
            {"id": 111, "name": "ACME", "emails": []},
        ],
        "has_more": True,
        "next_cursor": "CUR_C2",
    },
    "CUR_C2": {
        "items": [
            {"id": 222, "name": "Brady Groupe", "emails": ["compta@brady.fr"]},
        ],
        "has_more": False,
        "next_cursor": None,
    },
}

INVOICES_PAGES = {
    None: {
        "items": [
            {  # non soldée, avec client connu
                "id": 4641597078, "invoice_number": "260153",
                "label": "Facture BC SIGNAL ET DECO - 260153",
                "currency": "EUR", "amount": "1875.6",
                "remaining_amount_with_tax": "1875.6",
                "paid": False, "draft": False,
                "date": "2026-01-20", "deadline": "2026-03-02",
                "customer": {"id": 253399460, "url": f"{BASE_URL}/customers/253399460"},
            },
            {  # soldée -> exclue de list_open_invoices
                "id": 100, "invoice_number": "260100", "currency": "EUR",
                "amount": "500.0", "remaining_amount_with_tax": "0.0",
                "paid": True, "draft": False,
                "date": "2026-01-01", "deadline": "2026-02-01",
                "customer": {"id": 111},
            },
        ],
        "has_more": True,
        "next_cursor": "CUR_I2",
    },
    "CUR_I2": {
        "items": [
            {  # brouillon -> exclu de list_open_invoices même si remaining > 0
                "id": 101, "invoice_number": "DRAFT-1", "currency": "EUR",
                "amount": "999.0", "remaining_amount_with_tax": "999.0",
                "paid": False, "draft": True,
                "date": "2026-02-01", "deadline": None,
                "customer": {"id": 222},
            },
            {  # partiellement payée, client null
                "id": 102, "invoice_number": "260102", "currency": "EUR",
                "amount": "1000.0", "remaining_amount_with_tax": "400.0",
                "paid": False, "draft": False,
                "date": "2026-02-10", "deadline": "2026-03-10",
                "customer": None,
            },
        ],
        "has_more": False,
        "next_cursor": None,
    },
}

TRANSACTIONS_PAGES = {
    None: {
        "items": [
            {"id": 22146108600320, "date": "2026-06-01",
             "label": "Payment from Brady Groupe - 261022 261021",
             "amount": "3884.48", "currency": "EUR"},
            {"id": 999, "date": "2026-05-30",
             "label": "PRLV SEPA fournisseur", "amount": "-120.50",
             "currency": "EUR"},
        ],
        "has_more": False,
        "next_cursor": None,
    },
}


# --------------------------------------------------------------------------- #
# Transport mock : route les GET vers les payloads, refuse toute écriture
# --------------------------------------------------------------------------- #
def _page_for(pages: dict, request: httpx.Request) -> httpx.Response:
    cursor = parse_qs(request.url.query.decode()).get("cursor", [None])[0]
    return httpx.Response(200, json=pages[cursor])


def make_handler(calls: list[httpx.Request] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        # Aucune écriture ne doit jamais partir.
        assert request.method == "GET", f"écriture interdite: {request.method}"
        path = request.url.path
        if path.endswith("/customers"):
            return _page_for(CUSTOMERS_PAGES, request)
        if path.endswith("/customer_invoices"):
            return _page_for(INVOICES_PAGES, request)
        if path.endswith("/transactions"):
            return _page_for(TRANSACTIONS_PAGES, request)
        if "/customer_invoices/" in path:
            inv_id = int(path.rsplit("/", 1)[-1])
            for page in INVOICES_PAGES.values():
                for item in page["items"]:
                    if item["id"] == inv_id:
                        return httpx.Response(200, json=item)
            return httpx.Response(404, json={"error": "not found"})
        if "/customers/" in path:
            cid = int(path.rsplit("/", 1)[-1])
            for page in CUSTOMERS_PAGES.values():
                for item in page["items"]:
                    if item["id"] == cid:
                        return httpx.Response(200, json=item)
            return httpx.Response(404, json={"error": "not found"})
        return httpx.Response(404, json={"error": f"unhandled {path}"})

    return handler


@pytest.fixture
def calls() -> list[httpx.Request]:
    return []


@pytest.fixture
def client(calls) -> PennylaneClient:
    http = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(make_handler(calls)))
    c = PennylaneClient(token="test-token", base_url=BASE_URL, client=http)
    yield c
    c.close()


# --------------------------------------------------------------------------- #
# Auth / construction
# --------------------------------------------------------------------------- #
def test_bearer_token_header():
    c = PennylaneClient(token="secret-xyz", base_url=BASE_URL)
    assert c._client.headers["Authorization"] == "Bearer secret-xyz"
    assert c._client.headers["Accept"] == "application/json"
    c.close()


def test_token_defaults_to_config(monkeypatch):
    import config
    monkeypatch.setattr(config, "PENNYLANE_TOKEN", "from-env")
    c = PennylaneClient()
    assert c._token == "from-env"
    assert c._client.headers["Authorization"] == "Bearer from-env"
    c.close()


# --------------------------------------------------------------------------- #
# Customers
# --------------------------------------------------------------------------- #
def test_list_customers_paginates_all(client):
    customers = client.list_customers()
    assert [c.id for c in customers] == [253399460, 111, 222]
    assert all(isinstance(c, Customer) for c in customers)


def test_customer_email_from_emails_list(client):
    by_id = {c.id: c for c in client.list_customers()}
    assert by_id[253399460].email == "paie@signal.fr"
    assert by_id[111].email is None  # emails: []


# --------------------------------------------------------------------------- #
# Invoices
# --------------------------------------------------------------------------- #
def test_list_all_invoices_maps_fields(client):
    invoices = client.list_all_invoices()
    by_id = {i.id: i for i in invoices}
    assert len(invoices) == 4  # tout, brouillons et soldées comprises

    inv = by_id[4641597078]
    assert isinstance(inv, Invoice)
    assert inv.number == "260153"
    assert inv.customer_id == 253399460
    assert inv.customer_name == "SIGNAL ET DECO"  # joint depuis /customers
    assert inv.amount == Decimal("1875.6")
    assert inv.remaining_amount == Decimal("1875.6")
    assert inv.currency == "EUR"
    assert inv.paid is False
    assert inv.date == date(2026, 1, 20)
    assert inv.due_date == date(2026, 3, 2)


def test_list_open_invoices_filters_remaining_and_draft(client):
    invoices = client.list_open_invoices()
    ids = {i.id for i in invoices}
    # 4641597078 (remaining>0) et 102 (partielle) -> oui
    # 100 (soldée) et 101 (brouillon) -> non
    assert ids == {4641597078, 102}
    assert all(i.remaining_amount > 0 for i in invoices)


def test_open_invoice_partial_and_null_customer(client):
    inv = next(i for i in client.list_open_invoices() if i.id == 102)
    assert inv.remaining_amount == Decimal("400.0")
    assert inv.amount == Decimal("1000.0")
    assert inv.customer_id == 0      # customer null
    assert inv.customer_name == ""
    assert inv.due_date == date(2026, 3, 10)


def test_get_invoice_single(client):
    inv = client.get_invoice(4641597078)
    assert inv.number == "260153"
    assert inv.customer_name == "SIGNAL ET DECO"


def test_since_filter_sent_as_json(client, calls):
    client.list_all_invoices(since=date(2026, 1, 1))
    inv_call = next(r for r in calls if r.url.path.endswith("/customer_invoices"))
    flt = parse_qs(inv_call.url.query.decode())["filter"][0]
    assert json.loads(flt) == [
        {"field": "date", "operator": "gteq", "value": "2026-01-01"}]


def test_pagination_uses_cursor(client, calls):
    client.list_all_invoices()
    inv_calls = [r for r in calls if r.url.path.endswith("/customer_invoices")]
    assert len(inv_calls) == 2  # 2 pages
    cursors = [parse_qs(r.url.query.decode()).get("cursor", [None])[0]
               for r in inv_calls]
    assert cursors == [None, "CUR_I2"]


# --------------------------------------------------------------------------- #
# Transactions
# --------------------------------------------------------------------------- #
def test_list_bank_transactions_revolut_source(client):
    txs = client.list_bank_transactions()
    assert all(isinstance(t, BankTransaction) for t in txs)
    assert all(t.source == "revolut" for t in txs)


def test_transaction_credit_and_debit_sign(client):
    by_ref = {t.ref: t for t in client.list_bank_transactions()}
    credit = by_ref["22146108600320"]
    assert credit.credit == Decimal("3884.48")
    assert credit.debit is None
    assert credit.label.startswith("Payment from Brady Groupe")
    assert credit.value_date == date(2026, 6, 1)

    debit = by_ref["999"]
    assert debit.debit == Decimal("120.50")
    assert debit.credit is None


# --------------------------------------------------------------------------- #
# Lecture seule : aucune méthode publique n'écrit
# --------------------------------------------------------------------------- #
def test_no_write_methods_exist():
    forbidden = ("create", "update", "delete", "post", "put", "patch")
    public = [n for n in dir(PennylaneClient)
              if not n.startswith("_") and callable(getattr(PennylaneClient, n))]
    assert not [n for n in public if any(f in n.lower() for f in forbidden)]


# --------------------------------------------------------------------------- #
# Fenêtre temporelle : filtre date gteq ~90 jours par défaut
# --------------------------------------------------------------------------- #
def test_list_bank_transactions_default_lookback_window(client, calls, monkeypatch):
    monkeypatch.setattr(config, "REMINDER_LOOKBACK_DAYS", 90)
    client.list_bank_transactions()

    tx_call = next(r for r in calls if r.url.path.endswith("/transactions"))
    query = parse_qs(tx_call.url.query.decode())
    # Pas de tri sur date (l'API ne trie que sur id).
    assert "sort" not in query
    flt = json.loads(query["filter"][0])
    assert len(flt) == 1
    assert flt[0]["field"] == "date"
    assert flt[0]["operator"] == "gteq"

    expected = date.today() - timedelta(days=90)
    sent = date.fromisoformat(flt[0]["value"])
    # ~90 jours : on tolère 1 jour d'écart (bascule de minuit).
    assert abs((sent - expected).days) <= 1


# --------------------------------------------------------------------------- #
# Rate limit 429 : retry avec backoff puis succès
# --------------------------------------------------------------------------- #
def test_get_retries_on_429_then_succeeds(monkeypatch):
    # On n'attend pas réellement entre les tentatives.
    sleeps: list[float] = []
    monkeypatch.setattr(client_module.time, "sleep", lambda d: sleeps.append(d))

    responses = [
        httpx.Response(429, headers={"Retry-After": "1"}, json={"error": "rate"}),
        httpx.Response(429, json={"error": "rate"}),
        httpx.Response(200, json={"items": [], "has_more": False}),
    ]
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        resp = responses[attempts["n"]]
        attempts["n"] += 1
        return resp

    http = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    c = PennylaneClient(token="t", base_url=BASE_URL, client=http)
    try:
        payload = c._get("/transactions")
    finally:
        c.close()

    assert payload == {"items": [], "has_more": False}
    assert attempts["n"] == 3  # deux 429 + un 200
    # Retry-After respecté (1s), puis backoff 2 ** 1 = 2s.
    assert sleeps == [1.0, 2.0]
