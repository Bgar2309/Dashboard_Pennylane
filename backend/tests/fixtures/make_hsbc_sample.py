"""Génère un mini-XLSX HSBC d'exemple au format décrit dans le README.

À remplacer idéalement par un vrai relevé HSBC anonymisé (demander à Bruno).
En attendant, ce fichier produit `hsbc_sample.xlsx` reproduisant fidèlement
les particularités du format réel :
  - en-tête de compte répété au-dessus du tableau (IBAN/BIC/solde) -> à ignorer,
  - '?' parasites dans certains libellés (ex 'Tesla?FR?'),
  - lignes crédit ET débit, virements internes (EHS GROUP FRANCE / Treso) et frais
    bien présents (le parser est NEUTRE : il ne les exclut PAS).

Usage : python backend/tests/fixtures/make_hsbc_sample.py
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

COLUMNS = [
    "Date opération",
    "Date de valeur",
    "Libellé",
    "Référence client",
    "Référence bancaire",
    "Montant du débit",
    "Montant du crédit",
]

# Lignes "mouvement" : (op, valeur, libellé, ref client, ref bancaire, débit, crédit)
ROWS = [
    ("02/01/2026", "02/01/2026", "VIREMENT Tesla?FR? FACTURE 260001", "CLI-TESLA", "REF0001", "", "12 500,00"),
    ("03/01/2026", "03/01/2026", "VIREMENT EHS GROUP FRANCE Treso", "EHS-TRESO", "REF0002", "", "50 000,00"),
    ("05/01/2026", "06/01/2026", "FRAIS DE TENUE DE COMPTE", "", "REF0003", "18,50", ""),
    ("07/01/2026", "07/01/2026", "PRLV Fournisseur?XYZ?", "FRN-XYZ", "REF0004", "1 234,56", ""),
    ("09/01/2026", "10/01/2026", "VIREMENT CLIENT DUPONT SARL 260002", "CLI-DUPONT", "REF0005", "", "3 200,00"),
    ("12/01/2026", "12/01/2026", "VIREMENT EHS GROUP FRANCE Treso retour", "EHS-TRESO", "REF0006", "50 000,00", ""),
]


def build_workbook() -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Mouvements"

    # En-tête de compte répété / métadonnées -> doivent être ignorés par le parser.
    ws.append(["HSBC FRANCE - RELEVE DE COMPTE"])
    ws.append(["IBAN", "FR76 3000 0000 0000 0000 0000 000"])
    ws.append(["BIC", "CCFRFRPP"])
    ws.append(["Solde de clôture", "", "", "", "", "", "67 446,94"])
    ws.append([])

    # Vraie ligne d'en-tête de colonnes.
    ws.append(COLUMNS)

    for row in ROWS:
        ws.append(list(row))

    # En-tête de compte répété à nouveau en bas (cas réel HSBC) -> ignoré.
    ws.append([])
    ws.append(["IBAN", "FR76 3000 0000 0000 0000 0000 000"])
    return wb


def main() -> None:
    out = Path(__file__).with_name("hsbc_sample.xlsx")
    build_workbook().save(out)
    print(f"écrit : {out}")


if __name__ == "__main__":
    main()
