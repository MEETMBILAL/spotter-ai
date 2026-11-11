import { Suspense, lazy, useCallback, useMemo, useRef, useState } from "react";
import { analyzeTrip } from "./api/client";
import type { AnalyzeResponse, TripRequest } from "./api/types";
import { CheckpointDetail, CheckpointList } from "./components/CheckpointPanel";
import HeatmapControls from "./components/HeatmapControls";
import PlannerForm from "./components/PlannerForm";
import RecommendationPanel from "./components/RecommendationPanel";
import RouteList from "./components/RouteList";
import { useHeatmap } from "./hooks/useHeatmap";
import { trackEvent } from "./lib/analytics";
import type { HeatMetric } from "./lib/risk";

const MapView = lazy(() => import("./components/MapView")); // mapbox-gl is ~2 MB: load off the critical path

type Analysis = { status: "idle" } | { status: "loading" } | { status: "error"; message: string } | { status: "done"; data: AnalyzeResponse };

export default function App() {
  const [analysis, setAnalysis] = useState<Analysis>({ status: "idle" });
  const [request, setRequest] = useState<TripRequest | null>(null);
  const [analysisKey, setAnalysisKey] = useState(0);
  const [routeId, setRouteId] = useState<string | null>(null);
  const [cpIndex, setCpIndex] = useState<number | null>(null);
  const [heatOn, setHeatOn] = useState(false);
  const [hour, setHour] = useState(0);
  const [metric, setMetric] = useState<HeatMetric>("risk");
  const abort = useRef<AbortController | null>(null);

  const data = analysis.status === "done" ? analysis.data : null;
  const routes = data?.routes ?? [];
  const route = routes.find((r) => r.id === routeId) ?? null;
  const routeIndex = route ? routes.indexOf(route) : -1;
  const { state: heatState, retry } = useHeatmap(request, routeIndex, heatOn && !!data, analysisKey);

  const run = useCallback(async (req: TripRequest) => {
    abort.current?.abort();
    const ctrl = new AbortController();
    abort.current = ctrl;
    setAnalysis({ status: "loading" });
    setCpIndex(null);
    trackEvent("trip_analysis_start", {
      origin: req.origin.label,
      destination: req.destination.label,
      load_lb: req.load_lb,
      interval: req.checkpoint_interval_miles,
    });
    try {
      const d = await analyzeTrip(req, ctrl.signal);
      if (ctrl.signal.aborted) return;
      setRequest(req); setAnalysisKey((k) => k + 1); setHour(0);
      const chosenRouteId = d.recommendation.route_id ?? d.routes[0]?.id ?? null;
      setRouteId(chosenRouteId);
      setAnalysis({ status: "done", data: d });
      trackEvent("trip_analysis_success", {
        routes_found: d.routes.length,
        recommendation: d.recommendation.status,
        has_safe_route: d.recommendation.status !== "no_safe_route",
      });
    } catch (e) {
      if (ctrl.signal.aborted) return;
      const errorMsg = e instanceof Error ? e.message : "Something went wrong.";
      setAnalysis({ status: "error", message: errorMsg });
      trackEvent("trip_analysis_error", { message: errorMsg });
    }
  }, []);

  const heat = useMemo(() => (heatOn && heatState.status === "done" && heatState.data ? { data: heatState.data, hour, metric } : null),
    [heatOn, heatState, hour, metric]);
  const cp = route?.checkpoints.find((c) => c.index === cpIndex) ?? null;

  return (
    <div className="app">
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <header className="top" role="banner">
        <h1>Spotter <span>AI</span></h1>
        <p>Weather-aware commercial truck routing &amp; corridor risk intelligence</p>
      </header>
      <main id="main-content" className="layout" tabIndex={-1}>
        <div className="side">
          <PlannerForm loading={analysis.status === "loading"} onSubmit={run} />
          {analysis.status === "error" && <div className="panel error" role="alert" aria-live="assertive"><h2>Analysis failed</h2><p>{analysis.message}</p></div>}
          {analysis.status === "loading" && <div className="panel" role="status" aria-live="polite"><p>Finding routes and checking forecast along each one…</p></div>}
          {analysis.status === "idle" && (
            <>
              <div className="panel muted">
                <p>Enter origin, destination, load weight and departure time to compare commercial truck routes by real-time meteorological weather risk. All calculations derive from real forecast models; nothing is simulated.</p>
              </div>
              <section className="panel guide-card" aria-label="Why Weather-Aware Truck Routing">
                <h2>Why Spotter AI</h2>
                <p className="guide-desc">
                  Traditional navigation apps only tell you traffic delays. <strong>Spotter AI</strong> assesses weather hazards matched to your vehicle weight and specific checkpoint arrival times (ETA).
                </p>
                <div className="features-grid">
                  <div className="feature-item">
                    <strong>💨 Wind Rollover Prevention</strong>
                    <p>Calculates high crosswind blowover hazards calibrated to trailer weight (15k empty to 80k lbs fully loaded).</p>
                  </div>
                  <div className="feature-item">
                    <strong>❄️ Snow &amp; Blizzard Warnings</strong>
                    <p>Detects heavy snow accumulation rates and freezing temperatures across highway corridors.</p>
                  </div>
                  <div className="feature-item">
                    <strong>🛣️ 3-Route Risk Comparison</strong>
                    <p>Lexicographically compares up to 3 driving routes by miles of severe and high hazards to find the safest corridor.</p>
                  </div>
                </div>
              </section>
            </>
          )}
          {data && <>
            <RecommendationPanel data={data} />
            <RouteList routes={routes} selectedId={routeId} onSelect={(id) => {
              setRouteId(id);
              setCpIndex(null);
              trackEvent("route_selected", { route_id: id });
            }} />
            {route && <CheckpointList route={route} selected={cpIndex} onSelect={(idx) => {
              setCpIndex(idx);
              trackEvent("checkpoint_selected", { index: idx });
            }} />}
          </>}
        </div>
        <div className="map-pane">
          <div className="map-area">
            <Suspense fallback={<div className="map-missing" role="status" aria-live="polite">Loading interactive route map…</div>}><MapView routes={routes} selectedRouteId={routeId} selectedCheckpoint={cpIndex}
              onSelectRoute={(id) => {
                setRouteId(id);
                setCpIndex(null);
                trackEvent("map_route_selected", { route_id: id });
              }} onSelectCheckpoint={(idx) => {
                setCpIndex(idx);
                trackEvent("map_checkpoint_selected", { index: idx });
              }} heat={heat} /></Suspense>
          </div>
          {data && (
            <div className="overlays">
              {cp && <CheckpointDetail cp={cp} onClose={() => setCpIndex(null)} />}
              <HeatmapControls enabled={heatOn} onToggle={(v) => {
                setHeatOn(v);
                trackEvent("heatmap_toggled", { enabled: v });
              }} state={heatState} hour={hour} onHour={setHour}
                metric={metric} onMetric={(m) => {
                  setMetric(m);
                  trackEvent("heatmap_metric_changed", { metric: m });
                }} onRetry={retry} />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
