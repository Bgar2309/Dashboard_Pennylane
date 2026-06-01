# integration/pennylane
**Rôle** : wrapper REST Pennylane v2, LECTURE SEULE. Seul module qui parle à Pennylane.
**AVANT DE CODER** : lire https://pennylane.readme.io/reference (champs exacts, pagination cursor).
**Interface** : voir client.py (PennylaneClient). Bearer token = env PENNYLANE_TOKEN.
**Ne fait PAS** : aucun push (create/update/delete), pas de MCP, pas de matching, pas de DB.
**Dépend de** : core, env PENNYLANE_TOKEN. Lib : httpx.
