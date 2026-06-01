"""Constantes de filtrage métier HSBC. Listes éditables sans toucher au code.
Issu de l'analyse du relevé réel EHS.
"""
# Libellés = virements internes / trésorerie (à exclure du matching client)
INTERNAL_LABELS: list[str] = [
    "EHS GROUP FRANCE",  # virements internes / treso
    "TRESO",
]
# Libellés = frais bancaires / TVA / CB (pas des paiements clients)
FEE_LABELS: list[str] = [
    "ARRETE DE COMPTE",
    "FRAIS",
    "TVA/FACT MENSUELLE",
    "FACT MENSUELLE HT",
    "FACTURES CB",
    "COM. D'INTERVENTION",
]
# Détection des n° de facture EHS : 26xxxx / 261xxxx / "CA 26xxxxx"
INVOICE_NUMBER_REGEX = r"(?:CA\s*)?(26\d{4,5})"
