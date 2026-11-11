import type { AnalyzeResponse, GeocodeResult, HeatmapResponse, TripRequest } from "./types";

export class ApiError extends Error {
  constructor(public code: string, message: string, public status = 0) { super(message); }
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;

async function request<T>(path: string, init: RequestInit, check: (d: unknown) => boolean, timeoutMs = 90_000): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  const external = init.signal;
  external?.addEventListener("abort", () => ctrl.abort());
  let res: Response;
  try {
    res = await fetch(path, { ...init, signal: ctrl.signal, headers: { "Content-Type": "application/json", ...init.headers } });
  } catch (e) {
    if (external?.aborted) throw e;
    if (ctrl.signal.aborted) throw new ApiError("timeout", "The request timed out. Please try again.");
    throw new ApiError("network", "Could not reach the server. Check your connection.");
  } finally { clearTimeout(timer); }
  let data: unknown;
  try { data = await res.json(); } catch { data = null; }
  if (!res.ok) {
    const err = isObj(data) && isObj(data.error) ? data.error : null;
    const detail = err && isObj(err.details) ? Object.entries(err.details).map(([k, v]) => `${k}: ${[v].flat().join(" ")}`).join(" · ") : "";
    throw new ApiError(String(err?.code ?? "http_error"), `${String(err?.message ?? `Request failed (${res.status})`)}${detail ? " — " + detail : ""}`, res.status);
  }
  if (!check(data)) throw new ApiError("invalid_response", "The server returned an unexpected response.", res.status);
  return data as T;
}

export const isAnalyze = (d: unknown): boolean =>
  isObj(d) && Array.isArray(d.routes) && isObj(d.recommendation) && isObj(d.trip) &&
  d.routes.every((r) => isObj(r) && Array.isArray(r.checkpoints) && isObj(r.geometry) && isObj(r.summary) && isObj(r.ranking));
export const isHeatmap = (d: unknown): boolean =>
  isObj(d) && Array.isArray(d.points) && Array.isArray(d.frames) && d.frames.length === 49;

export const analyzeTrip = (body: TripRequest, signal?: AbortSignal) =>
  request<AnalyzeResponse>("/api/analyze", { method: "POST", body: JSON.stringify(body), signal }, isAnalyze);

export const fetchHeatmap = (body: TripRequest, routeIndex: number, signal?: AbortSignal) =>
  request<HeatmapResponse>("/api/heatmap", { method: "POST", body: JSON.stringify({ ...body, route_index: routeIndex }), signal }, isHeatmap);

export const geocode = (q: string, signal?: AbortSignal) =>
  request<{ results: GeocodeResult[] }>(`/api/geocode?q=${encodeURIComponent(q)}`, { signal },
    (d) => isObj(d) && Array.isArray(d.results), 15_000).then((d) => d.results);
