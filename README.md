# Relance EHS

Dashboard de relance client basé sur Pennylane (vérité comptable, lecture seule) +
rapprochement bancaire HSBC local pour ne jamais relancer un client déjà payé.

## Architecture
Voir `ARCHITECTURE.md` (modules, interfaces, vagues de parallélisation).
Voir `AGENTS.md` (prompts à coller dans N terminaux Claude Code).

## Backend (FastAPI)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Variables : PENNYLANE_TOKEN, DATABASE_PATH, CORS_ORIGINS
uvicorn api.main:app --reload --port 8000
```

## Frontend (React + Vite)
```bash
cd ui
npm install
echo "VITE_API_BASE=http://localhost:8000" > .env
npm run dev
```

## Déploiement Railway
2 services : `relance-api` (backend, volume monté sur /data pour SQLite) et `relance-front` (ui).
Variables VITE_* : ARG + ENV dans le Dockerfile AVANT `npm run build`.

## Règles non négociables
- Pennylane = lecture seule. Aucun push (pas de lettrage, pas de création).
- L'historique des relances n'est loggé QUE via POST /api/reminders/{cid}/confirm.
- Pas de pandas-ta / ta-lib.
