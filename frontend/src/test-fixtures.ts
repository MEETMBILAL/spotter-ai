import type { AnalyzeResponse, Checkpoint, HeatmapResponse, Route } from "./api/types";

const rv = (level: number | null, label: string) => ({ level, label });
export const cp = (index: number, over: Partial<Checkpoint> = {}): Checkpoint => ({
  index, distance_miles: index * 25, lon: -100 + index, lat: 40, eta: "2026-11-12T14:00:00Z", is_origin: index === 0, is_destination: false,
  weather: { status: "ok", reason: null, wind_mph: 12, rain_in_hr: 0, snow_in_hr: 0 },
  risk: { wind: rv(0, "Low"), rain: rv(0, "Low"), snow: rv(0, "Low"), final: rv(0, "Low"), complete: true, load_override_applied: false }, ...over,
});
export const route = (id: string, over: Partial<Route> = {}): Route => ({
  id, name: `Route ${id.slice(-1)}`, distance_miles: 100, duration_s: 7200, eta_method: "segment",
  geometry: { type: "LineString", coordinates: [[-100, 40], [-99, 40]] }, checkpoints: [cp(0), cp(1)],
  summary: { total_miles: 100, miles_by_risk: { Low: 80, Moderate: 0, High: 15, Severe: 5, "No Travel": 0, Unknown: 0 }, unknown_miles: 0, average_risk: 0.3, has_no_travel: false, data_complete: true },
  ranking: { rank: 1, eligible: true, ineligible_reason: null, decided_by: null, recommended: false }, ...over,
});
export const analysis = (over: Partial<AnalyzeResponse> = {}): AnalyzeResponse => ({
  trip: { origin: { label: "A", lon: -100, lat: 40 }, destination: { label: "B", lon: -96, lat: 40 }, departure_time: "2026-11-12T14:00:00Z", load_lb: 40000, checkpoint_interval_miles: 25 },
  routes: [route("route-1", { ranking: { rank: 1, eligible: true, ineligible_reason: null, decided_by: "duration", recommended: true } }), route("route-2")],
  recommendation: { status: "recommended", message: "Safest eligible route", route_id: "route-1", reasons: ["Selected because it has the shortest travel time"], warnings: [] },
  warnings: [], meta: { routes_returned: 2, routes_requested: 3, truck_specific_routing: false }, ...over,
});
export const heatmap = (): HeatmapResponse => ({
  route_id: "route-1", departure_time: "2026-11-12T14:00:00Z", points: [[-100, 40], [-99, 40]], warnings: [], unavailable_hours: [],
  note: "Regional weather around the route corridor (no truck-load rules).",
  frames: Array.from({ length: 49 }, (_, h) => ({ hour: h, time: new Date(Date.UTC(2026, 10, 12, 14 + h)).toISOString(),
    wind_mph: [10, 20], rain_in_hr: [0, 0], snow_in_hr: [0, 0], risk: [0, 1], available: h < 40 })),
});
