import type { Route } from "../api/types";
import { fmtDuration, fmtMi } from "../lib/format";
import { RISK_COLORS, RISK_LABELS, ROUTE_COLORS, UNKNOWN_COLOR } from "../lib/risk";

export function MileBar({ route }: { route: Route }) {
  const parts = [...RISK_LABELS.map((l, i) => ({ l, c: RISK_COLORS[i] })), { l: "Unknown", c: UNKNOWN_COLOR }];
  const total = route.summary.total_miles || 1;
  return (
    <div className="milebar" role="img" aria-label={parts.map((p) => `${p.l} ${fmtMi(route.summary.miles_by_risk[p.l] ?? 0)}`).join(", ")}>
      {parts.map((p) => { const m = route.summary.miles_by_risk[p.l] ?? 0; return m > 0 ? <span key={p.l} style={{ width: `${(m / total) * 100}%`, background: p.c }} /> : null; })}
    </div>
  );
}

interface Props { routes: Route[]; selectedId: string | null; onSelect: (id: string) => void }

export default function RouteList({ routes, selectedId, onSelect }: Props) {
  return (
    <section className="panel" aria-labelledby="routes-h">
      <h2 id="routes-h">Routes</h2>
      <div role="radiogroup" aria-labelledby="routes-h" className="routes">
        {routes.map((r, i) => {
          const m = r.summary.miles_by_risk;
          return (
            <button key={r.id} role="radio" aria-checked={r.id === selectedId} className={`route ${r.id === selectedId ? "sel" : ""}`} onClick={() => onSelect(r.id)}>
              <span className="swatch" style={{ background: ROUTE_COLORS[i % 3] }} aria-hidden />
              <span className="route-main">
                <span className="route-title">{r.name}
                  {r.ranking.recommended && <b className="tag good">Recommended</b>}
                  {r.summary.has_no_travel && <b className="tag bad">No Travel</b>}
                  {!r.summary.data_complete && <b className="tag warn">Partial weather</b>}
                </span>
                <span className="muted">{fmtMi(r.distance_miles)} · {fmtDuration(r.duration_s)}{r.ranking.rank ? ` · Rank ${r.ranking.rank}` : ""}</span>
                <MileBar route={r} />
                <span className="stats">
                  <span>Severe <b>{fmtMi(m["Severe"] ?? 0)}</b></span>
                  <span>High <b>{fmtMi(m["High"] ?? 0)}</b></span>
                  <span>Mod <b>{fmtMi(m["Moderate"] ?? 0)}</b></span>
                  <span>Low <b>{fmtMi(m["Low"] ?? 0)}</b></span>
                  {r.summary.unknown_miles > 0 && <span>Unknown <b>{fmtMi(r.summary.unknown_miles)}</b></span>}
                  <span>Avg risk <b>{r.summary.average_risk === null ? "n/a" : `${r.summary.average_risk.toFixed(2)} / 4`}</b></span>
                </span>
                {r.ranking.ineligible_reason && <span className="muted small">Not eligible: {r.ranking.ineligible_reason}</span>}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
