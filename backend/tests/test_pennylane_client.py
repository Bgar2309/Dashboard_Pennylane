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

# Comptes auxiliaires clients (/ledger_accounts) : on garde les ``customer``,
# on écarte le générique « Clients » (4111) et le compte ``reserved`` e-commerce.
LEDGER_ACCOUNTS_PAGES = {
    None: {
        "items": [
            {"id": 1001, "number": "411SIGN", "label": "SIGNAL ET DECO",
             "type": "customer", "enabled": True, "letterable": True},
        ],
        "has_more": True,
        "next_cursor": "CUR_LA2",
    },
    "CUR_LA2": {
        "items": [
            {"id": 1002, "number": "411BRAD", "label": "Brady Groupe",
             "type": "customer", "enabled": True, "letterable": True},
            {"id": 9999, "number": "4111", "label": "Clients",
             "type": "customer", "enabled": True, "letterable": True},
            {"id": 8888, "number": "41106001", "label": "Clients e-commerce",
             "type": "reserved", "enabled": True, "letterable": True},
            {"id": 7777, "number": "41106",
             "label": "Clients - Numéros standards",
             "type": "customer", "enabled": True, "letterable": True},
            {"id": 6666, "number": "411OLD", "label": "Ancien client",
             "type": "customer", "enabled": False, "letterable": True},
        ],
        "has_more": False,
        "next_cursor": None,
    },
}

# Lignes d'écriture (/ledger_entry_lines), indexées par compte client.
# lettered_ledger_entry_lines.ids vide == ligne ouverte ; rempli == soldée.
LEDGER_LINES_BY_ACCOUNT = {
    1001: [
        {  # ouverte, débitrice -> devient une Invoice (SIGNAL ET DECO)
            "id": 5001, "label": "FAC 260153", "debit": "1875.6", "credit": "0.0",
            "date": "2026-01-20",
            "ledger_account": {"id": 1001, "number": "411SIGN"},
            "ledger_entry": {"id": 70001},
            "lettered_ledger_entry_lines": {"ids": [], "url": None}},
        {  # lettrée (ids remplis) -> soldée -> exclue
            "id": 5002, "label": "FAC 260100", "debit": "500.0", "credit": "0.0",
            "date": "2026-01-01",
            "ledger_account": {"id": 1001, "number": "411SIGN"},
            "ledger_entry": {"id": 70000},
            "lettered_ledger_entry_lines": {"ids": [123, 124], "url": f"{BASE_URL}/x"}},
    ],
    1002: [
        {  # ouverte mais au crédit (montant <= 0) -> acompte/avoir -> ignorée
            "id": 5003, "label": "Acompte", "debit": "0.0", "credit": "300.0",
            "date": "2026-02-05",
            "ledger_account": {"id": 1002, "number": "411BRAD"},
            "ledger_entry": {"id": 70002},
            "lettered_ledger_entry_lines": {"ids": [], "url": None}},
        {  # ouverte, débitrice, sans libellé -> number = id de l'écriture
            "id": 5004, "label": "", "debit": "1000.0", "credit": "0.0",
            "date": "2026-02-10",
            "ledger_account": {"id": 1002, "number": "411BRAD"},
            "ledger_entry": {"id": 70003},
            "lettered_ledger_entry_lines": {"ids": [], "url": None}},
    ],
}


def _ledger_lines_response(request: httpx.Request) -> httpx.Response:
    """Sert les lignes du compte ciblé par le filtre ledger_account_id."""
    flt = parse_qs(request.url.query.decode()).get("filter", ["[]"])[0]
    account_id = None
    for cond in json.loads(flt):
        if cond.get("field") == "ledger_account_id":
            account_id = cond.get("value")
    items = LEDGER_LINES_BY_ACCOUNT.get(account_id, [])
    return httpx.Response(200, json={"items": items, "has_more": False,
                                     "next_cursor": None})


# Écritures du journal de banque HSBC (BQ1, id 6716577). Triées -date, limit 1 :
# la frontière comptable = date de la 1re (la plus récente).
HSBC_JOURNAL_ID = 6716577
LEDGER_ENTRIES_RESPONSE = {
    "items": [{"id": 80001, "date": "2026-04-30", "journal_id": HSBC_JOURNAL_ID}],
    "has_more": False,
    "next_cursor": None,
}
# Réponse vide (aucune écriture) -> frontière None. Activé par le test au besoin.
_ledger_entries_payload = {"current": LEDGER_ENTRIES_RESPONSE}


def _ledger_entries_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=_ledger_entries_payload["current"])


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
        if path.endswith("/ledger_accounts"):
            return _page_for(LEDGER_ACCOUNTS_PAGES, request)
        if path.endswith("/ledger_entry_lines"):
            return _ledger_lines_response(request)
        if path.endswith("/ledger_entries"):
            return _ledger_entries_response(request)
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


def test_get_invoice_single(client):
    inv = client.get_invoice(4641597078)
    assert inv.number == "260153"
    assert inv.customer_name == "SIGNAL ET DECO"


# --------------------------------------------------------------------------- #
# Encours client via le grand livre : /ledger_accounts + /ledger_entry_lines
# --------------------------------------------------------------------------- #
def test_list_customer_ledger_accounts_excludes_generic_and_reserved(client):
    """Seuls les comptes ``customer`` non génériques et actifs sont retenus."""
    accounts = client.list_customer_ledger_accounts()
    assert accounts == {1001: "SIGNAL ET DECO", 1002: "Brady Groupe"}
    # Le générique 4111 (« Clients ») et le reserved 41106001 sont écartés.
    assert 9999 not in accounts and 8888 not in accounts
    # Le générique 41106 (« Clients - Numéros standards ») est écarté.
    assert 7777 not in accounts
    # Le compte désactivé (enabled == False) est écarté.
    assert 6666 not in accounts


def test_list_customer_ledger_accounts_filter_and_sort(client, calls):
    client.list_customer_ledger_accounts()
    call = next(r for r in calls if r.url.path.endswith("/ledger_accounts"))
    query = parse_qs(call.url.query.decode())
    assert query["sort"] == ["id"]  # seul tri accepté par l'API
    assert json.loads(query["filter"][0]) == [
        {"field": "number", "operator": "start_with", "value": "411"}]


def test_list_open_receivable_lines_excludes_lettered(client):
    """Une ligne lettrée (ids non vides) est exclue ; les ouvertes sont gardées."""
    lines = client.list_open_receivable_lines()
    ids = {l["id"] for l in lines}
    # 5002 est lettrée -> exclue. 5001, 5003 (crédit), 5004 sont ouvertes.
    assert ids == {5001, 5003, 5004}
    assert 5002 not in ids


def test_list_open_invoices_from_open_ledger_lines(client):
    """Chaque ligne ouverte débitrice devient une Invoice avec le bon nom."""
    invoices = client.list_open_invoices()
    by_id = {i.id: i for i in invoices}
    # 5003 est un crédit (acompte non lettré) -> ignoré ; 5002 lettrée -> exclu.
    assert set(by_id) == {5001, 5004}

    sig = by_id[5001]
    assert isinstance(sig, Invoice)
    assert sig.customer_id == 1001
    assert sig.customer_name == "SIGNAL ET DECO"
    assert sig.number == "FAC 260153"
    assert sig.amount == Decimal("1875.6")
    assert sig.remaining_amount == Decimal("1875.6")
    assert sig.currency == "EUR"
    assert sig.paid is False
    assert sig.date == date(2026, 1, 20)
    # due_date = date + 30 jours (conditions "30_days" par défaut).
    assert sig.due_date == date(2026, 1, 20) + timedelta(days=30)


def test_open_invoice_number_falls_back_to_entry_id(client):
    """Sans libellé exploitable, le numéro = id de l'écriture (jamais inventé)."""
    inv = next(i for i in client.list_open_invoices() if i.id == 5004)
    assert inv.number == "70003"  # ledger_entry.id
    assert inv.customer_name == "Brady Groupe"
    assert inv.amount == Decimal("1000.0")
    assert inv.due_date == date(2026, 2, 10) + timedelta(days=30)


def test_open_invoices_ignore_unlettered_credit(client):
    """Un crédit ouvert isolé (montant <= 0) n'est pas une créance à relancer."""
    ids = {i.id for i in client.list_open_invoices()}
    assert 5003 not in ids


def test_list_open_invoices_lines_filtered_by_account(client, calls):
    """Les lignes sont paginées par compte (filtre ledger_account_id eq)."""
    client.list_open_invoices()
    line_calls = [r for r in calls if r.url.path.endswith("/ledger_entry_lines")]
    accounts_queried = set()
    for r in line_calls:
        flt = json.loads(parse_qs(r.url.query.decode())["filter"][0])
        for cond in flt:
            if cond["field"] == "ledger_account_id":
                assert cond["operator"] == "eq"
                accounts_queried.add(cond["value"])
    assert accounts_queried == {1001, 1002}


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
# Frontière comptable HSBC (journal BQ1)
# --------------------------------------------------------------------------- #
def test_hsbc_accounting_boundary_returns_last_entry_date(client):
    """La frontière = date de la dernière écriture du journal HSBC (BQ1)."""
    _ledger_entries_payload["current"] = LEDGER_ENTRIES_RESPONSE
    assert client.hsbc_accounting_boundary() == date(2026, 4, 30)


def test_hsbc_accounting_boundary_query_filters_journal_sort_limit(client, calls):
    """Filtre journal_id eq 6716577, tri -date, limit 1 (pas de page/per_page)."""
    _ledger_entries_payload["current"] = LEDGER_ENTRIES_RESPONSE
    client.hsbc_accounting_boundary()
    call = next(r for r in calls if r.url.path.endswith("/ledger_entries"))
    query = parse_qs(call.url.query.decode())
    assert query["sort"] == ["-date"]
    assert query["limit"] == ["1"]
    assert "page" not in query and "per_page" not in query
    assert json.loads(query["filter"][0]) == [
        {"field": "journal_id", "operator": "eq", "value": 6716577}]


def test_hsbc_accounting_boundary_none_when_empty(client):
    """Aucune écriture dans le journal -> frontière None."""
    _ledger_entries_payload["current"] = {
        "items": [], "has_more": False, "next_cursor": None}
    try:
        assert client.hsbc_accounting_boundary() is None
    finally:
        _ledger_entries_payload["current"] = LEDGER_ENTRIES_RESPONSE


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
