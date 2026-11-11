import type { HeatState } from "../hooks/useHeatmap";
import type { HeatMetric } from "../lib/risk";
import { fmtTime } from "../lib/format";

interface Props {
  enabled: boolean; onToggle: (v: boolean) => void; state: HeatState; hour: number; onHour: (h: number) => void;
  metric: HeatMetric; onMetric: (m: HeatMetric) => void; onRetry: () => void;
}

export default function HeatmapControls({ enabled, onToggle, state, hour, onHour, metric, onMetric, onRetry }: Props) {
  const frame = state.data?.frames[hour];
  return (
    <section className="heat" aria-label="Weather heatmap">
      <div className="heat-head">
        <label className="switch"><input type="checkbox" checked={enabled} onChange={(e) => onToggle(e.target.checked)} /> Weather heatmap (48 h)</label>
        {enabled && (
          <select aria-label="Heatmap metric" value={metric} onChange={(e) => onMetric(e.target.value as HeatMetric)}>
            <option value="risk">Weather risk</option><option value="wind">Wind</option><option value="rain">Rain</option><option value="snow">Snow</option>
          </select>
        )}
      </div>
      {enabled && state.status === "loading" && <p className="muted" role="status">Loading 49 hourly forecast frames…</p>}
      {enabled && state.status === "error" && <p className="field-error" role="alert">{state.error} <button className="link" onClick={onRetry}>Retry</button></p>}
      {enabled && state.status === "done" && state.data && (
        <>
          <div className="slider">
            <label htmlFor="hour">Forecast hour</label>
            <input id="hour" type="range" min={0} max={48} step={1} value={hour} onChange={(e) => onHour(Number(e.target.value))}
              aria-valuetext={`+${hour} hours, ${frame ? fmtTime(frame.time) : ""}`} />
            <output htmlFor="hour" aria-live="polite" aria-atomic="true">{hour === 0 ? "Departure" : `+${hour} h`}{frame ? ` · ${fmtTime(frame.time)}` : ""}</output>
          </div>
          {frame && !frame.available && <p className="warn-line">⚠ No forecast data for this hour (beyond the provider’s coverage).</p>}
          {state.data.points.length === 0 && <p className="muted">No heatmap points for this route.</p>}
          {state.data.warnings.map((w) => <p key={w} className="warn-line">⚠ {w}</p>)}
          <p className="muted small">{state.data.note}</p>
        </>
      )}
    </section>
  );
}
