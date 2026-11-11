// DISPLAY ONLY. Risk levels are computed by the backend; this maps a level number to colour/label.
export const RISK_COLORS = ["#2e9e6a", "#d9b310", "#ee8a1f", "#d13b2b", "#5b1456"] as const;
export const UNKNOWN_COLOR = "#7d8793";
export const RISK_LABELS = ["Low", "Moderate", "High", "Severe", "No Travel"] as const;
export const riskColor = (level: number | null) => (level === null ? UNKNOWN_COLOR : RISK_COLORS[level] ?? UNKNOWN_COLOR);
export const ROUTE_COLORS = ["#1f6feb", "#8a4fff", "#0f9aa8"] as const;
// Heatmap intensity scaling (visual only): fraction of the "No Travel" threshold.
export const HEAT_SCALE = { risk: 4, wind: 55, rain: 1, snow: 3 } as const;
export type HeatMetric = keyof typeof HEAT_SCALE;
