import type { Checkpoint, Route } from "../api/types";
import { fmtMi, fmtNum, fmtTime } from "../lib/format";
import { riskColor } from "../lib/risk";

export function RiskBadge({ level, label }: { level: number | null; label: string }) {
  return <span className="badge" style={{ background: riskColor(level) }}>{label}</span>;
}

export function CheckpointDetail({ cp, onClose }: { cp: Checkpoint; onClose: () => void }) {
  const w = cp.weather;
  return (
    <aside className="detail" aria-label="Checkpoint details">
      <header>
        <h3>{cp.is_origin ? "Origin" : cp.is_destination ? "Destination" : `Checkpoint ${cp.index}`} · {fmtMi(cp.distance_miles)}</h3>
        <button className="icon" onClick={onClose} aria-label="Close checkpoint details">×</button>
      </header>
      <p className="muted">ETA {fmtTime(cp.eta)} · {cp.lat.toFixed(3)}, {cp.lon.toFixed(3)}</p>
      <p>Final risk: <RiskBadge level={cp.risk.final.level} label={cp.risk.final.label} />
        {cp.risk.load_override_applied && <span className="muted small"> (raised by load rule)</span>}</p>
      <table>
        <thead><tr><th>Factor</th><th>Value</th><th>Risk</th></tr></thead>
        <tbody>
          <tr><th scope="row">Wind</th><td>{fmtNum(w.wind_mph, "mph", 1)}</td><td><RiskBadge level={cp.risk.wind.level} label={cp.risk.wind.label} /></td></tr>
          <tr><th scope="row">Rain</th><td>{fmtNum(w.rain_in_hr, "in/hr")}</td><td><RiskBadge level={cp.risk.rain.level} label={cp.risk.rain.label} /></td></tr>
          <tr><th scope="row">Snow</th><td>{fmtNum(w.snow_in_hr, "in/hr")}</td><td><RiskBadge level={cp.risk.snow.level} label={cp.risk.snow.label} /></td></tr>
        </tbody>
      </table>
      {w.status !== "ok" && <p className="warn-line">⚠ Weather {w.status === "unavailable" ? "unavailable" : "partly unavailable"}
        {w.reason === "forecast_not_covered" ? ": arrival is outside the forecast range." : "."}</p>}
    </aside>
  );
}

export function CheckpointList({ route, selected, onSelect }: { route: Route; selected: number | null; onSelect: (i: number) => void }) {
  return (
    <section className="panel" aria-labelledby="cp-h">
      <h2 id="cp-h">{route.name} checkpoints</h2>
      <ol className="cps">
        {route.checkpoints.map((c) => (
          <li key={c.index}>
            <button className={c.index === selected ? "sel" : ""} onClick={() => onSelect(c.index)} aria-pressed={c.index === selected}>
              <span className="mi">{fmtMi(c.distance_miles)}</span>
              <span className="muted">{fmtTime(c.eta)}</span>
              <RiskBadge level={c.risk.final.level} label={c.risk.final.label} />
            </button>
          </li>
        ))}
      </ol>
      <p className="muted small">ETA = departure + provider route duration (no traffic, rest stops or hours-of-service).
        {route.eta_method === "proportional" ? " Interpolated by distance." : " Uses segment-level durations."}</p>
    </section>
  );
}
