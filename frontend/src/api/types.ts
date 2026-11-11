export interface Place { label: string; lon: number; lat: number }
export interface RiskValue { level: number | null; label: string }
export interface CheckpointWeather {
  status: "ok" | "partial" | "unavailable"; reason: string | null;
  wind_mph: number | null; rain_in_hr: number | null; snow_in_hr: number | null;
}
export interface Checkpoint {
  index: number; distance_miles: number; lon: number; lat: number; eta: string;
  is_origin: boolean; is_destination: boolean; weather: CheckpointWeather;
  risk: { wind: RiskValue; rain: RiskValue; snow: RiskValue; final: RiskValue; complete: boolean; load_override_applied: boolean };
}
export interface RouteSummary {
  total_miles: number; miles_by_risk: Record<string, number>; unknown_miles: number;
  average_risk: number | null; has_no_travel: boolean; data_complete: boolean;
}
export interface RouteRanking { rank: number | null; eligible: boolean; ineligible_reason: string | null; decided_by: string | null; recommended: boolean }
export interface Route {
  id: string; name: string; distance_miles: number; duration_s: number; eta_method: "segment" | "proportional";
  geometry: { type: "LineString"; coordinates: [number, number][] };
  checkpoints: Checkpoint[]; summary: RouteSummary; ranking: RouteRanking;
}
export interface Recommendation { status: "recommended" | "recommended_partial_data" | "no_safe_route" | "insufficient_data"; message: string; route_id: string | null; reasons: string[]; warnings: string[] }
export interface AnalyzeResponse {
  trip: { origin: Place; destination: Place; departure_time: string; load_lb: number; checkpoint_interval_miles: number };
  routes: Route[]; recommendation: Recommendation; warnings: string[];
  meta: { routes_returned: number; routes_requested: number; truck_specific_routing: boolean };
}
export interface HeatmapFrame { hour: number; time: string; wind_mph: (number | null)[]; rain_in_hr: (number | null)[]; snow_in_hr: (number | null)[]; risk: (number | null)[]; available: boolean }
export interface HeatmapResponse { route_id: string; departure_time: string; points: [number, number][]; frames: HeatmapFrame[]; unavailable_hours: number[]; warnings: string[]; note: string }
export interface GeocodeResult { id: string; name: string; label: string; lon: number; lat: number }
export interface TripRequest { origin: Place; destination: Place; departure_time: string; load_lb: number; checkpoint_interval_miles: 10 | 25 | 50 }
