# core
**Rôle** : modèles de données partagés (dataclasses + enums) et helpers purs d'aging.
**Expose** : Customer, Invoice, BankTransaction, PaymentMatch, ReminderLogEntry,
CustomerDunningRow, ReminderLevel, AgingBucket, MatchConfidence, bucket_for(), level_for().
**Ne fait PAS** : aucun I/O, aucun réseau, aucune DB, aucune logique métier complexe.
**Dépend de** : rien. ✅ DÉJÀ IMPLÉMENTÉ (models.py + aging.py complets).
