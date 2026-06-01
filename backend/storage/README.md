# storage
**Rôle** : persistance SQLite (reminders_log, payment_matches, invoice_cache, cache_meta).
**Interface** : voir db.py (Storage). log_reminder est le SEUL point d'écriture de l'historique.
**Ne fait PAS** : pas de calcul d'aging, pas de matching, pas de réseau.
**Dépend de** : core, env DATABASE_PATH.
