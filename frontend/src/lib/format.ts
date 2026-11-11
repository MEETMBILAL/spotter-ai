export const fmtDuration = (s: number) => {
  const m = Math.round(s / 60);
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
};
// NOTE: ETAs are shown in the user's local timezone. This is intentional — drivers
// read their device's clock. The ETA source (departure_time ISO string) is UTC-offset-aware.
export const fmtTime = (iso: string) =>
  new Date(iso).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" });
export const fmtMi = (n: number) => `${n.toLocaleString(undefined, { maximumFractionDigits: 1 })} mi`;
export const fmtNum = (n: number | null, unit: string, digits = 2) => (n === null ? "Unavailable" : `${n.toFixed(digits)} ${unit}`);
export const toLocalInput = (d: Date) => {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
};
