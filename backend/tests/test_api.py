"""Tests d'API : TestClient FastAPI avec services mockés (dependency_overrides).

On ne teste PAS la logique métier (couverte ailleurs) : on vérifie que chaque
endpoint câble la bonne dépendance, valide l'entrée et sérialise la sortie.
Critère : /api/health 200, chaque endpoint répond.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from api import deps
from api.main import app
from core.models import (AgingBucket, Customer, CustomerDunningRow,
                         CustomerStatement, Invoice, MatchConfidence,
                         PaymentMatch, ReminderLevel, ReminderLogEntry,
                         StatementEntry)

TODAY = date(2026, 6, 1)


# --------------------------------------------------------------------------- #
# Doubles de test (mocks minimalistes respectant les interfaces appelées)
# --------------------------------------------------------------------------- #
def _invoice(**kw) -> Invoice:
    base = dict(
        id=1, number="260604", customer_id=10, customer_name="GALLIN",
        date=date(2026, 3, 1), due_date=date(2026, 4, 1),
        amount=Decimal("1200.00"), currency="EUR", paid=False,
        remaining_amount=Decimal("1200.00"),
    )
    base.update(kw)
    return Invoice(**base)


def _row(**kw) -> CustomerDunningRow:
    base = dict(
        customer=Customer(id=10, name="GALLIN", email="a@b.fr"),
        open_invoices=[_invoice()],
        total_due=Decimal("1200.00"),
        oldest_due_date=date(2026, 4, 1),
        worst_bucket=AgingBucket.D30_60,
        suggested_level=ReminderLevel.SECOND,
        last_reminder=None,
        blocked_by_payment=False,
    )
    base.update(kw)
    return CustomerDunningRow(**base)


class FakeLedger:
    def build_dunning_rows(self, today):
        return [_row()]

    def get_open_invoices(self, use_cache=True, max_cache_age_s=1800):
        return [_invoice(), _invoice(id=2, customer_id=99, number="260900")]

    def build_statement(self, customer_id):
        if customer_id == 404:
            return CustomerStatement(
                customer=Customer(id=customer_id, name=""),
                entries=[], final_balance=Decimal("0"),
            )
        return CustomerStatement(
            customer=Customer(id=customer_id, name="GALLIN", email=None),
            entries=[
                StatementEntry(
                    date=date(2026, 3, 1), type="facture", label="Facture 260604",
                    number="260604", debit=Decimal("1200.00"), credit=None,
                    balance=Decimal("1200.00"),
                ),
                StatementEntry(
                    date=date(2026, 3, 20), type="paiement",
                    label="Règlement facture 260604", number="260604",
                    debit=None, credit=Decimal("1000.00"),
                    balance=Decimal("200.00"),
                ),
            ],
            final_balance=Decimal("200.00"),
        )


class FakeReminders:
    def __init__(self):
        self.confirmed: list[tuple] = []

    def dunning_view(self, today, hsbc_txs=None, min_days_between_reminders=8):
        return [_row(blocked_by_payment=True)]

    def generate_draft(self, customer_id, today):
        if customer_id == 404:
            raise ValueError(f"Aucune facture ouverte pour le client {customer_id}")
        return f"Objet : Relance\nClient {customer_id}\nTotal dû : 1 200,00 €"

    def confirm_sent(self, customer_id, level, invoice_numbers, note=None):
        self.confirmed.append((customer_id, level, invoice_numbers, note))
        return ReminderLogEntry(
            id=1, customer_id=customer_id, customer_name="GALLIN",
            level=level, sent_at=datetime(2026, 6, 1, 10, 0, 0),
            invoice_numbers=list(invoice_numbers), note=note,
        )


class FakeBankMatch:
    def match(self, txs, open_invoices):
        return [PaymentMatch(
            bank_ref="REF1", invoice_id=1, invoice_number="260604",
            customer_name="GALLIN", amount=Decimal("1200.00"),
            confidence=MatchConfidence.STRONG,
            matched_invoice_numbers=["260604"], reason="ok",
        )]


class FakeStorage:
    def __init__(self):
        self.saved: list = []

    def list_reminders(self, customer_id=None, limit=100):
        return [ReminderLogEntry(
            id=1, customer_id=10, customer_name="GALLIN",
            level=ReminderLevel.FIRST, sent_at=datetime(2026, 5, 1, 9, 0),
            invoice_numbers=["260604"], note=None,
        )]

    def save_matches(self, matches):
        self.saved.extend(matches)

    def list_matches(self, since=None):
        return [PaymentMatch(
            bank_ref="REF1", invoice_id=1, invoice_number="260604",
            customer_name="GALLIN", amount=Decimal("1200.00"),
            confidence=MatchConfidence.STRONG,
            matched_invoice_numbers=["260604"], reason="ok",
        )]


class FakeStats:
    def __init__(self):
        self.ledger = FakeLedger()

    def dashboard_kpis(self, rows, today=None):
        return {
            "encours_total": Decimal("1200.00"),
            "clients_a_relancer": 1,
            "dso_approche": Decimal("92.0"),
            "retard_moyen_pondere": Decimal("61.0"),
            "total_par_bucket": {b.value: Decimal("0") for b in AgingBucket},
        }

    def aging_distribution(self, rows):
        return {b.value: Decimal("0") for b in AgingBucket}

    def top_overdue(self, rows, n=10):
        return [{
            "customer_id": 10, "customer_name": "GALLIN",
            "total_due": Decimal("1200.00"), "worst_bucket": "30-60",
            "oldest_due_date": date(2026, 4, 1), "suggested_level": "second",
            "open_invoices_count": 1,
        }]


@pytest.fixture
def client():
    fakes = {
        "ledger": FakeLedger(),
        "reminders": FakeReminders(),
        "bank": FakeBankMatch(),
        "storage": FakeStorage(),
        "stats": FakeStats(),
    }
    app.dependency_overrides[deps.get_ledger_service] = lambda: fakes["ledger"]
    app.dependency_overrides[deps.get_reminder_service] = lambda: fakes["reminders"]
    app.dependency_overrides[deps.get_bank_match_service] = lambda: fakes["bank"]
    app.dependency_overrides[deps.get_storage] = lambda: fakes["storage"]
    app.dependency_overrides[deps.get_stats_service] = lambda: fakes["stats"]
    # Pas de context manager -> le lifespan (init_schema) ne tourne pas en test.
    test_client = TestClient(app)
    test_client.fakes = fakes
    yield test_client
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_get_ledger(client):
    resp = client.get("/api/ledger", params={"today": TODAY.isoformat()})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["customer"]["name"] == "GALLIN"
    assert body[0]["worst_bucket"] == "30-60"


def test_get_customer_invoices(client):
    resp = client.get("/api/ledger/10")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["customer_id"] == 10


def test_get_customer_invoices_404(client):
    resp = client.get("/api/ledger/12345")
    assert resp.status_code == 404


def test_get_customer_statement(client):
    resp = client.get("/api/ledger/10/statement")
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer"]["id"] == 10
    assert body["final_balance"] == "200.00"
    assert len(body["entries"]) == 2
    assert body["entries"][0]["type"] == "facture"
    assert body["entries"][1]["type"] == "paiement"
    assert body["entries"][1]["credit"] == "1000.00"


def test_get_customer_statement_404(client):
    resp = client.get("/api/ledger/404/statement")
    assert resp.status_code == 404


def test_get_reminders(client):
    resp = client.get("/api/reminders", params={"today": TODAY.isoformat()})
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["blocked_by_payment"] is True


def test_get_draft(client):
    resp = client.get("/api/reminders/10/draft")
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_id"] == 10
    assert "Total dû" in body["draft"]


def test_get_draft_404(client):
    resp = client.get("/api/reminders/404/draft")
    assert resp.status_code == 404


def test_confirm_sent_logs(client):
    payload = {"level": "second", "invoice_numbers": ["260604"], "note": "ok"}
    resp = client.post("/api/reminders/10/confirm", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["customer_id"] == 10
    assert body["level"] == "second"
    # confirm_sent est bien le déclencheur du log
    assert client.fakes["reminders"].confirmed == [
        (10, ReminderLevel.SECOND, ["260604"], "ok")
    ]


def test_confirm_sent_validation_error(client):
    resp = client.post("/api/reminders/10/confirm",
                       json={"level": "not-a-level"})
    assert resp.status_code == 422


def test_get_history(client):
    resp = client.get("/api/reminders/history")
    assert resp.status_code == 200
    assert resp.json()[0]["customer_name"] == "GALLIN"


def test_bank_upload(client, monkeypatch):
    # Le parsing HSBC est testé ailleurs : on le neutralise ici (bytes factices).
    monkeypatch.setattr("api.routers.bank.parse_hsbc",
                        lambda file_bytes, filename: [])
    files = {"file": ("releve.xlsx", b"fake-bytes",
                      "application/vnd.ms-excel")}
    resp = client.post("/api/bank/upload", files=files)
    assert resp.status_code == 201
    body = resp.json()
    assert body[0]["confidence"] == "strong"
    # les matchs sont persistés via storage
    assert len(client.fakes["storage"].saved) == 1


def test_bank_upload_rejects_bad_extension(client):
    files = {"file": ("releve.txt", b"x", "text/plain")}
    resp = client.post("/api/bank/upload", files=files)
    assert resp.status_code == 400


def test_get_matches(client):
    resp = client.get("/api/bank/matches")
    assert resp.status_code == 200
    assert resp.json()[0]["bank_ref"] == "REF1"


def test_get_stats(client):
    resp = client.get("/api/stats", params={"today": TODAY.isoformat()})
    assert resp.status_code == 200
    body = resp.json()
    assert body["clients_a_relancer"] == 1
    assert "total_par_bucket" in body
    assert body["top_overdue"][0]["customer_name"] == "GALLIN"
