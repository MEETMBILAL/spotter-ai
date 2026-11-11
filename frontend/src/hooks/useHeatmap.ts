import { useEffect, useRef, useState } from "react";
import { fetchHeatmap } from "../api/client";
import type { HeatmapResponse, TripRequest } from "../api/types";

export type HeatState = { status: "idle" | "loading" | "error" | "done"; data?: HeatmapResponse; error?: string };

/** Fetches the 49-frame heatmap once per (analysis, route); slider movement never hits the network. */
export function useHeatmap(req: TripRequest | null, routeIndex: number, enabled: boolean, analysisKey: number) {
  const cache = useRef(new Map<string, HeatmapResponse>());
  const lastKey = useRef(analysisKey);
  const [state, setState] = useState<HeatState>({ status: "idle" });
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (lastKey.current !== analysisKey) { cache.current.clear(); lastKey.current = analysisKey; }
    if (!enabled || !req || routeIndex < 0) { setState({ status: "idle" }); return; }
    const key = `${analysisKey}:${routeIndex}`;
    const hit = cache.current.get(key);
    if (hit) { setState({ status: "done", data: hit }); return; }
    const ctrl = new AbortController();
    setState({ status: "loading" });
    fetchHeatmap(req, routeIndex, ctrl.signal)
      .then((d) => { cache.current.set(key, d); setState({ status: "done", data: d }); })
      .catch((e) => { if (!ctrl.signal.aborted) setState({ status: "error", error: e instanceof Error ? e.message : "Heatmap failed" }); });
    return () => ctrl.abort();
  }, [req, routeIndex, enabled, analysisKey, retry]);

  return { state, retry: () => setRetry((n) => n + 1) };
}
