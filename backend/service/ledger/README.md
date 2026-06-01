# service/ledger
**Rôle** : grand livre client à un instant T (aging + agrégation par client).
**Interface** : LedgerService(pennylane, storage) -> get_open_invoices, aging_for, build_dunning_rows.
**Ne fait PAS** : pas de texte de relance, pas de matching bancaire, pas d'HTTP direct.
**Dépend de** : core, integration/pennylane, storage.
