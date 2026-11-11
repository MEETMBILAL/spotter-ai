import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { useEffect, useRef, useState } from "react";
import type { HeatmapResponse, Route } from "../api/types";
import { HEAT_SCALE, RISK_COLORS, RISK_LABELS, ROUTE_COLORS, UNKNOWN_COLOR, riskColor, type HeatMetric } from "../lib/risk";

const TOKEN = import.meta.env.VITE_MAPBOX_PUBLIC_TOKEN as string | undefined;
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

interface Props {
  routes: Route[]; selectedRouteId: string | null; selectedCheckpoint: number | null;
  onSelectRoute: (id: string) => void; onSelectCheckpoint: (i: number) => void;
  heat: { data: HeatmapResponse; hour: number; metric: HeatMetric } | null;
}

export default function MapView({ routes, selectedRouteId, selectedCheckpoint, onSelectRoute, onSelectCheckpoint, heat }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const cb = useRef({ onSelectRoute, onSelectCheckpoint });
  cb.current = { onSelectRoute, onSelectCheckpoint };

  // One-time map construction. Everything afterwards is setData/setFilter (no re-creation).
  useEffect(() => {
    if (!TOKEN || !box.current) return;
    mapboxgl.accessToken = TOKEN;
    const map = new mapboxgl.Map({ container: box.current, style: "mapbox://styles/mapbox/light-v11", center: [-98, 39], zoom: 3.3, attributionControl: true });
    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => {
      for (const id of ["heat", "routes", "checkpoints"]) map.addSource(id, { type: "geojson", data: EMPTY });
      map.addLayer({ id: "heat", type: "heatmap", source: "heat", paint: {
        "heatmap-weight": ["get", "w"], "heatmap-intensity": 1,
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 3, 30, 7, 70, 10, 110],
        "heatmap-opacity": 0.8,
        "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"], 0, "rgba(46,158,106,0)", 0.2, "rgba(46,158,106,0.4)",
          0.45, "rgba(217,179,16,0.6)", 0.7, "rgba(238,138,31,0.72)", 1, "rgba(209,59,43,0.85)"] } });
      map.addLayer({ id: "routes-casing", type: "line", source: "routes", filter: ["==", ["get", "selected"], true],
        layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#fff", "line-width": 10 } });
      map.addLayer({ id: "routes-unselected", type: "line", source: "routes", filter: ["==", ["get", "selected"], false],
        layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": ["get", "color"], "line-width": 5, "line-opacity": 0.55 } });
      map.addLayer({ id: "routes-selected", type: "line", source: "routes", filter: ["==", ["get", "selected"], true],
        layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": ["get", "color"], "line-width": 6 } });
      map.addLayer({ id: "checkpoints", type: "circle", source: "checkpoints", paint: {
        "circle-radius": ["case", ["get", "end"], 9, 6], "circle-color": ["get", "color"], "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
      map.addLayer({ id: "checkpoint-selected", type: "circle", source: "checkpoints", filter: ["==", ["get", "index"], -1], paint: {
        "circle-radius": 13, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#0b2530", "circle-stroke-width": 3 } });
      for (const layer of ["routes-unselected", "checkpoints"]) {
        map.on("mouseenter", layer, () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", layer, () => { map.getCanvas().style.cursor = ""; });
      }
      map.on("click", "routes-unselected", (e) => { const id = e.features?.[0]?.properties?.id; if (id) cb.current.onSelectRoute(String(id)); });
      map.on("click", "checkpoints", (e) => { const i = e.features?.[0]?.properties?.index; if (i !== undefined) cb.current.onSelectCheckpoint(Number(i)); });
      setReady(true);
    });
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; setReady(false); };
  }, []);

  // Routes + checkpoints of the selected route
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    (map.getSource("routes") as mapboxgl.GeoJSONSource).setData({
      type: "FeatureCollection",
      features: routes.map((r, i) => ({ type: "Feature", geometry: r.geometry, properties: { id: r.id, color: ROUTE_COLORS[i % 3], selected: r.id === selectedRouteId } })),
    });
    const sel = routes.find((r) => r.id === selectedRouteId);
    (map.getSource("checkpoints") as mapboxgl.GeoJSONSource).setData(!sel ? EMPTY : {
      type: "FeatureCollection",
      features: sel.checkpoints.map((c) => ({ type: "Feature", geometry: { type: "Point", coordinates: [c.lon, c.lat] },
        properties: { index: c.index, color: riskColor(c.risk.final.level), end: c.is_origin || c.is_destination } })),
    });
  }, [ready, routes, selectedRouteId]);

  // Fit to the selected route only when the selection/analysis changes
  useEffect(() => {
    const map = mapRef.current;
    const sel = routes.find((r) => r.id === selectedRouteId);
    if (!ready || !map || !sel) return;
    const b = new mapboxgl.LngLatBounds();
    sel.geometry.coordinates.forEach((c) => b.extend(c as [number, number]));
    const compact = window.innerWidth < 900;
    map.fitBounds(b, { padding: compact ? 30 : { top: 60, bottom: 130, left: 60, right: 60 }, duration: 600, maxZoom: 11 });
  }, [ready, routes, selectedRouteId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setFilter("checkpoint-selected", ["==", ["get", "index"], selectedCheckpoint ?? -1]);
  }, [ready, selectedCheckpoint, selectedRouteId]);

  // Heatmap frame: data is already in memory; slider only swaps the GeoJSON of one source
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const src = map.getSource("heat") as mapboxgl.GeoJSONSource;
    if (!heat) { src.setData(EMPTY); return; }
    const f = heat.data.frames[heat.hour];
    const values = heat.metric === "risk" ? f.risk : heat.metric === "wind" ? f.wind_mph : heat.metric === "rain" ? f.rain_in_hr : f.snow_in_hr;
    const scale = HEAT_SCALE[heat.metric];
    const features: GeoJSON.Feature[] = [];
    heat.data.points.forEach((p, i) => {
      const v = values[i];
      if (v === null || v === undefined) return;       // unavailable points are omitted, never drawn as "calm"
      features.push({ type: "Feature", geometry: { type: "Point", coordinates: p }, properties: { w: Math.min(1, v / scale) } });
    });
    src.setData({ type: "FeatureCollection", features });
  }, [ready, heat]);

  if (!TOKEN) {
    return (
      <div className="map-missing" role="note">
        <h3>Map unavailable</h3>
        <p>Set <code>VITE_MAPBOX_PUBLIC_TOKEN</code> in <code>frontend/.env</code> (a public <code>pk.</code> token) and restart. Routes and checkpoints are still listed in the panels.</p>
      </div>
    );
  }
  return (
    <>
      <div ref={box} className="map" role="region" aria-label="Route map" />
      <Legend heat={!!heat} />
    </>
  );
}

function Legend({ heat }: { heat: boolean }) {
  return (
    <div className="legend" aria-label="Map legend">
      <strong>Checkpoint risk</strong>
      <ul>{RISK_LABELS.map((l, i) => <li key={l}><i style={{ background: RISK_COLORS[i] }} />{l}</li>)}<li><i style={{ background: UNKNOWN_COLOR }} />Unknown</li></ul>
      {heat && <p className="small">Heatmap: regional weather around the corridor, independent of your load.</p>}
    </div>
  );
}
