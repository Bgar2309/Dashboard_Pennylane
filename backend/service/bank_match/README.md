# service/bank_match
**Rôle** : cœur "ne jamais relancer un client déjà payé". Filtre + détecte n° facture + matche 3 niveaux.
**Interface** : BankMatchService(storage) -> is_client_payment, extract_invoice_numbers, match, covered_invoice_ids.
Constantes éditables dans filters.py (INTERNAL_LABELS, FEE_LABELS, INVOICE_NUMBER_REGEX).
**Ne fait PAS** : ne parse pas les fichiers (hsbc_parser), n'écrit pas dans Pennylane, pas de texte.
**Dépend de** : core, storage. Fuzzy : rapidfuzz.
