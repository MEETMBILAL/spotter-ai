# PROJECT_STATE (end of build session)

## Status
All planned features implemented. **Not verified against real Mapbox / Open-Meteo, not visually checked in a browser, not deployed.**

## Test results (actual, Linux container, Python 3.12 / Node 22)
- Backend: `pytest` -> 129 passed (all provider HTTP mocked with `responses`)
- Frontend: `tsc --noEmit` clean; `vitest` -> 27 passed; `vite build` succeeded
- Smoke test: gunicorn + WhiteNoise served SPA at `/`, `/api/health` OK, bad Host header -> 400, missing token -> JSON 503, validation -> JSON 400
- `pip-audit`: no known vulnerabilities (runtime + test deps). `npm audit --omit=dev`: 0. `npm audit` (dev tooling: vitest/vite/esbuild chain): 6 findings (3 moderate, 1 high, 2 critical) - dev-server/test tooling only, not in the production bundle; not fixed (would need major upgrades).

## Requirements matrix
| Area | Status | Evidence / Problem |
|---|---|---|
| 1 Risk calcs + ranking | PASS | boundary tests for wind/rain/snow, overrides (strict >), lexicographic ranking, all-blocked |
| 2 Real API integrations | UNVERIFIED | Implemented + mocked tests. Needs real tokens: run /api/geocode and /api/analyze for a real trip. Mapbox v6 geocode field names and `annotations=duration` alignment were written from docs knowledge and must be confirmed live |
| 3 Checkpoints/ETA/mileage | PASS (logic) | tiling, destination handling, scaling, ETA tests. Real-geometry accuracy UNVERIFIED |
| 4 Map + heatmap | PARTIAL | Code typechecks/builds; 49-frame data + slider logic tested. Mapbox GL rendering, layer styling, fit-bounds and performance NOT seen in a browser |
| 5 Front/back integration | PARTIAL | Typed client + contract tests on both sides; no live end-to-end browser run |
| 6 Security/perf/responsive | PARTIAL | Validation, size cap (413), rate limits, allowed hosts, no stack traces, token never logged, same-origin (no CORS). Responsive CSS + a11y (labels, combobox, radiogroup, keyboard list) written but not device-tested. Rate limit is per-process |
| 7 Deploy + docs | PARTIAL | Config, build.sh, Procfile, README, ASSUMPTIONS done. Not deployed. Response serializers are plain dicts (request serializers only) |

## Known gaps / remaining work
1. Add tokens, run real trip, confirm Mapbox alternatives (up to 3) + geocoding + heatmap on a phone browser.
2. Deploy (Render/Railway), set env vars, record Loom.
3. Termux: untested (all packages are pure Python; mapbox/Vite run on Node).
4. Decision to confirm: partial-data routes rank after complete-data routes (see ASSUMPTIONS).
5. Open-Meteo free tier is non-commercial.

## Files
backend/ (config, routing/{domain,providers,services,api,tests}), frontend/src/{api,components,hooks,lib,styles}, docs/ASSUMPTIONS.md, README.md, build.sh, Procfile.
