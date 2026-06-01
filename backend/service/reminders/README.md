# service/reminders
**Rôle** : orchestrateur de la vue relances. Combine ledger + bank_match + storage (+ drafts).
**Interface** : ReminderService(...) -> dunning_view, generate_draft (NE LOGUE RIEN), confirm_sent (SEUL point de log).
**drafts.py** (DraftGenerator) : templates FR déterministes, ton par niveau. Pas de LLM, pas d'I/O.
**Ne fait PAS** : pas d'envoi email réel, pas d'appel Pennylane direct (passe par ledger).
**Dépend de** : core, service/ledger, service/bank_match, drafts, storage.
