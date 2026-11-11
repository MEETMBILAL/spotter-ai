import { useEffect, useState } from "react";
import { geocode } from "../api/client";
import type { GeocodeResult } from "../api/types";

export function useGeocode(query: string, enabled: boolean) {
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const q = query.trim();
    if (!enabled || q.length < 3) { setResults([]); setLoading(false); setError(null); return; }
    const ctrl = new AbortController();
    setLoading(true);
    const t = setTimeout(() => {
      geocode(q, ctrl.signal)
        .then((r) => { setResults(r); setError(null); })
        .catch((e) => { if (!ctrl.signal.aborted) { setResults([]); setError(e instanceof Error ? e.message : "Search failed"); } })
        .finally(() => { if (!ctrl.signal.aborted) setLoading(false); });
    }, 300);
    return () => { clearTimeout(t); ctrl.abort(); };
  }, [query, enabled]);
  return { results, loading, error };
}
