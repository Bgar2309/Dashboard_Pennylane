"""Parser robuste des relevés HSBC (XLSX + PDF) -> list[BankTransaction].
NEUTRE : rend toutes les lignes de mouvement, ne filtre pas le métier (interne/frais).
Le filtrage est fait dans service/bank_match.

Colonnes XLSX attendues : Libellé, Référence client, Montant du crédit, Montant du débit,
Date de valeur, Date opération, Référence bancaire. En-têtes de compte répétés -> ignorés.
Normaliser l'encodage (remplacer les '?' parasites type 'Tesla?FR?'). Dates DD/MM/YYYY.
"""
from core.models import BankTransaction


def parse_hsbc_xlsx(file_bytes: bytes) -> list[BankTransaction]:
    raise NotImplementedError


def parse_hsbc_pdf(file_bytes: bytes) -> list[BankTransaction]:
    """pdfplumber, extraction de tableaux. Best-effort : ne pas planter sur ligne ambiguë."""
    raise NotImplementedError


def parse_hsbc(file_bytes: bytes, filename: str) -> list[BankTransaction]:
    """Dispatch selon extension (.xlsx/.xls -> xlsx ; .pdf -> pdf)."""
    raise NotImplementedError
