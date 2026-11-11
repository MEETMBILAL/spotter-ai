import type { Place } from "../api/types";

export interface FormValues { origin: Place | null; destination: Place | null; departure: string; loadLb: string; interval: 10 | 25 | 50 }
export type FormErrors = Partial<Record<"origin" | "destination" | "departure" | "loadLb", string>>;

export function validateForm(v: FormValues, now = new Date()): FormErrors {
  const e: FormErrors = {};
  if (!v.origin) e.origin = "Choose an origin from the suggestions.";
  if (!v.destination) e.destination = "Choose a destination from the suggestions.";
  if (v.origin && v.destination && Math.abs(v.origin.lat - v.destination.lat) < 0.005 && Math.abs(v.origin.lon - v.destination.lon) < 0.005)
    e.destination = "Origin and destination must differ.";
  const t = new Date(v.departure).getTime();
  if (!v.departure || Number.isNaN(t)) e.departure = "Enter a departure date and time.";
  else if (t < now.getTime() - 24 * 3600e3) e.departure = "Departure is too far in the past for a forecast.";
  else if (t > now.getTime() + 15 * 24 * 3600e3) e.departure = "Forecasts only extend about 15 days ahead.";
  const load = Number(v.loadLb);
  if (v.loadLb.trim() === "" || !Number.isFinite(load) || load < 0 || load > 200_000) e.loadLb = "Enter a load between 0 and 200,000 lb.";
  return e;
}
