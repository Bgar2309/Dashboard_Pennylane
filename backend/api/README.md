# api
**Rôle** : endpoints FastAPI (routers ledger/reminders/bank/stats). Validation + appel service + sérialisation.
**Construire en 1er** : api/schemas.py (Pydantic) + api/deps.py (injection) avant les routers.
**Endpoints** : voir ARCHITECTURE.md. POST /api/reminders/{cid}/confirm = SEUL déclencheur de log.
**Ne fait PAS** : zéro logique métier. Le parsing HSBC est délégué à hsbc_parser via bank_match.
**Dépend de** : tous les service/*, core.
