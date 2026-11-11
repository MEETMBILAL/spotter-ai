#!/usr/bin/env bash
# Production build: React bundle -> backend/frontend_dist, then Django collectstatic.
# Requires VITE_MAPBOX_PUBLIC_TOKEN (public pk.* token) in the environment or frontend/.env at build time.
set -euo pipefail
cd "$(dirname "$0")"
(cd frontend && npm ci && npm run build)
rm -rf backend/frontend_dist && cp -r frontend/dist backend/frontend_dist
cd backend && pip install -r requirements.txt && python manage.py collectstatic --noinput
