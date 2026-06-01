# integration/hsbc_parser
**Rôle** : parser robuste des relevés HSBC (XLSX + PDF) -> list[BankTransaction]. NEUTRE.
**Interface** : parse_hsbc(file_bytes, filename), parse_hsbc_xlsx, parse_hsbc_pdf.
Colonnes XLSX : Libellé, Référence client, Montant du crédit/débit, Date de valeur/opération.
En-têtes de compte répétés -> ignorer. Normaliser encodage ('?' parasites). Dates DD/MM/YYYY.
**Ne fait PAS** : pas de filtrage métier (interne/frais), pas de matching, pas de Pennylane, pas de DB.
**Dépend de** : core. Libs : openpyxl/pandas (xlsx), pdfplumber (pdf).
