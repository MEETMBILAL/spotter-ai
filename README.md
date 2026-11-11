# Spotter AI - weather-aware truck routing

Compare up to 3 driving routes by weather risk along the way, for your departure time and load weight.
React + TypeScript + Mapbox GL (frontend) / Django 5.2 + DRF (backend). Real Mapbox routing/geocoding and Open-Meteo forecasts only; no mock data is ever shown as real.

## Features
- Origin/destination autocomplete, departure date/time, load (lb), checkpoint interval 10/25/50 mi
- Provider routes (up to 3; if fewer are returned the UI says so, no routes are fabricated)
- Weather at each checkpoint's ETA; wind/rain/snow risk + load overrides; mileage-owned risk totals
- Lexicographic ranking (Severe mi, High mi, avg risk, time); any No Travel mileage = ineligible; "No Safe Route Available"
- Map with route layers, risk-coloured checkpoints, legend; checkpoint details; keyboard-usable checkpoint list
- 48-hour heatmap (49 frames, one request, slider is client-side) with loading/empty/error/unavailable states

## Architecture
`backend/routing/domain` pure Python (risk, geo, eta, segments, ranking, weather matching) -> `services` (analysis, heatmap) -> `providers` (Mapbox, Open-Meteo) -> `api` (DRF). All risk logic lives only in `domain/risk.py`; the frontend only displays backend results.

## Local setup (Termux or Linux)
    cd backend && python -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env     # set MAPBOX_SERVER_TOKEN (private sk./pk. token used server-side only)
    python manage.py runserver
    # second terminal
    cd frontend && cp .env.example .env   # set VITE_MAPBOX_PUBLIC_TOKEN (public pk. token, URL-restricted)
    npm install && npm run dev            # proxies /api to :8000

## Tests
    cd backend && DJANGO_DEBUG=true python -m pytest -q     # 129 tests, all HTTP mocked
    cd frontend && npm run typecheck && npm test && npm run build

## API
- `GET /api/health`
- `GET /api/geocode?q=` -> `{results:[{id,name,label,lon,lat}]}`
- `POST /api/analyze` `{origin:{label,lon,lat}, destination, departure_time (ISO with offset), load_lb, checkpoint_interval_miles}` -> trip, routes (geometry, checkpoints, risk, segments, summary, ranking), recommendation, warnings
- `POST /api/heatmap` same body + `route_index` -> 49 frames over corridor points
Errors: `{error:{code,message,details}}`. Rate limits: analyze 10/min, heatmap 20/min, geocode 60/min per IP.

## Production / deploy
`./build.sh` builds React into `backend/frontend_dist` and runs collectstatic; Django+WhiteNoise serves SPA and API from one origin (no CORS needed). Start: `cd backend && gunicorn config.wsgi:application -c gunicorn.conf.py` (see `Procfile`).
Required env: `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `MAPBOX_SERVER_TOKEN`; build-time `VITE_MAPBOX_PUBLIC_TOKEN`. Host behind HTTPS (e.g. Render/Railway/Fly). **Deployment has not been performed.**

## GitHub
    git init && git add . && git commit -m "Spotter AI" && git remote add origin <your-repo-url> && git push -u origin main
(`.env`, node_modules, venv, build outputs are git-ignored.)

## Tokens
Public (browser): `VITE_MAPBOX_PUBLIC_TOKEN`. Private (server only): `MAPBOX_SERVER_TOKEN`. Open-Meteo needs no key (free tier is non-commercial; use a commercial plan for production).
