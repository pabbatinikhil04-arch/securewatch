# SecureWatch

## What changed in this update
1. **Fixed the Dashboard/Websites/Alerts tabs** — they were dead links with no view-switching logic behind them. See `SECURITY_AUDIT.md` for details.
2. **New color palette** (teal/indigo) across the UI.
3. **Security hardening** — CORS fix, nginx reverse proxy + security headers on the frontend, secrets no longer hardcoded in `docker-compose.yml`, JWT moved from `localStorage` to `sessionStorage`. Full checklist walk-through in `SECURITY_AUDIT.md`.

## Run it
```bash
cp .env.example .env
# edit .env: set POSTGRES_PASSWORD and SECRET_KEY to real random values
#   openssl rand -hex 32   ← use this to generate SECRET_KEY

docker compose up --build
```
Then open **http://localhost** (the frontend nginx container — it proxies `/api` to the backend for you, so this is the only URL you need).

The backend is also reachable directly at `http://localhost:8000` for debugging/Postman use.

## Deploying to Render (backend + Postgres + frontend, all working)

This repo includes `render.yaml` so Render can create all three pieces from one Blueprint.

1. Push this repo to GitHub.
2. In Render: **New > Blueprint**, point it at the repo. Render reads `render.yaml` and creates:
   - `securewatch-db` — managed Postgres
   - `securewatch-backend` — the FastAPI app (built from `backend/Dockerfile`), with `DATABASE_URL` and `SECRET_KEY` set automatically
   - `securewatch-frontend` — the static frontend
3. **First deploy will fail CORS** until the two URLs know about each other (chicken-and-egg):
   - Once `securewatch-frontend` gets its URL (e.g. `https://securewatch-frontend.onrender.com`), confirm it matches `ALLOWED_ORIGINS` in `render.yaml` / the backend's env vars on Render — update it if Render assigned a different subdomain, then redeploy the backend.
   - Once `securewatch-backend` gets its URL (e.g. `https://securewatch-backend.onrender.com`), edit `frontend/config.js`:
     ```js
     window.__API_BASE_URL__ = 'https://securewatch-backend.onrender.com';
     ```
     Commit and push — Render redeploys the frontend automatically.
4. Open the frontend URL. Register a user, and everything (dashboard, websites, scans, alerts) should work end-to-end.

Note: Render's free tier spins down idle services — the first request after inactivity can take ~30–60s to wake the backend up.

## Project layout
```
securewatch/
├── docker-compose.yml
├── nginx.conf              # frontend reverse proxy + security headers
├── .env.example            # copy to .env, fill in real secrets
├── SECURITY_AUDIT.md        # checklist walkthrough
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example         # only used if you run uvicorn directly, without docker-compose
│   └── app/                 # FastAPI app package
└── frontend/
    ├── index.html
    ├── app.js
    └── style.css
```
