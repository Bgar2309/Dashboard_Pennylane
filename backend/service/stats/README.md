# service/stats
**Rôle** : KPIs dashboard (encours total, DSO, retard moyen, top retardataires, répartition aging).
**Interface** : StatsService(ledger, storage) -> dashboard_kpis, aging_distribution, top_overdue.
**Ne fait PAS** : pas de calcul d'aging brut (consomme des CustomerDunningRow), pas d'écriture, pas de réseau.
**Dépend de** : core, service/ledger, storage.
