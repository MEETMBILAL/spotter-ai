import type { AnalyzeResponse } from "../api/types";

export default function RecommendationPanel({ data }: { data: AnalyzeResponse }) {
  const rec = data.recommendation;
  const route = data.routes.find((r) => r.id === rec.route_id);
  const tone = rec.status === "recommended" ? "good" : rec.status === "recommended_partial_data" ? "warn" : "bad";
  const title = route ? `${route.name} — ${rec.message}` : rec.message;
  return (
    <section className={`panel rec ${tone}`} aria-labelledby="rec-h" role="status">
      <h2 id="rec-h">{rec.status === "no_safe_route" ? "No Safe Route Available" : rec.status === "insufficient_data" ? "Weather data unavailable" : "Recommendation"}</h2>
      <p className="rec-title">{title}</p>
      {rec.reasons.map((r) => <p key={r}>{r}.</p>)}
      {rec.status === "no_safe_route" && <p>Every available route contains No Travel conditions. Routes are shown for information only.</p>}
      {rec.status === "insufficient_data" && <p>Without forecast data, no route can be confirmed safe. Try again shortly.</p>}
      {[...rec.warnings, ...data.warnings].map((w) => <p key={w} className="warn-line">⚠ {w}</p>)}
    </section>
  );
}
