"""Variables d'environnement centralisées. Aucun secret hardcodé."""
import os

PENNYLANE_TOKEN = os.environ.get("PENNYLANE_TOKEN", "")
PENNYLANE_BASE_URL = os.environ.get(
    "PENNYLANE_BASE_URL", "https://app.pennylane.com/api/external/v2")
# Fenêtre temporelle (en jours) pour la récupération des transactions bancaires.
REMINDER_LOOKBACK_DAYS = int(os.environ.get("REMINDER_LOOKBACK_DAYS", "90"))
# Encours client : la fenêtre de rapprochement débit/crédit démarre au 1er janvier
# de (année courante − offset). Avec offset = 1, on part du 1er janvier de l'année
# N-1 : cette fenêtre inclut déjà les reports « A-Nouveau » de l'exercice, donc le
# solde d'ouverture, sans avoir à remonter au-delà.
RECEIVABLE_WINDOW_START_YEAR_OFFSET = int(
    os.environ.get("RECEIVABLE_WINDOW_START_YEAR_OFFSET", "1"))
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/data/relance.db")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
