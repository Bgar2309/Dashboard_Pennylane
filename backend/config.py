"""Variables d'environnement centralisées. Aucun secret hardcodé."""
import os

PENNYLANE_TOKEN = os.environ.get("PENNYLANE_TOKEN", "")
PENNYLANE_BASE_URL = os.environ.get(
    "PENNYLANE_BASE_URL", "https://app.pennylane.com/api/external/v2")
# Fenêtre temporelle (en jours) pour la récupération des transactions bancaires.
REMINDER_LOOKBACK_DAYS = int(os.environ.get("REMINDER_LOOKBACK_DAYS", "90"))
DATABASE_PATH = os.environ.get("DATABASE_PATH", "/data/relance.db")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
