"""Configuration pytest commune : ajoute `backend/` au sys.path pour que les
imports applicatifs (`core`, `integration`, ...) fonctionnent en test."""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
