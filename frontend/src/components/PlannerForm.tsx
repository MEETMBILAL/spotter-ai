import { useState } from "react";
import type { Place, TripRequest } from "../api/types";
import { toLocalInput } from "../lib/format";
import { validateForm, type FormErrors } from "../lib/validate";
import LocationInput from "./LocationInput";

function defaultDeparture() {
  const d = new Date(Date.now() + 3600e3);
  d.setMinutes(0, 0, 0);
  return toLocalInput(d);
}

export default function PlannerForm({ loading, onSubmit }: { loading: boolean; onSubmit: (r: TripRequest) => void }) {
  const [origin, setOrigin] = useState<Place | null>(null);
  const [destination, setDestination] = useState<Place | null>(null);
  const [departure, setDeparture] = useState(defaultDeparture);
  const [loadLb, setLoadLb] = useState("40000");
  const [interval, setIntervalMi] = useState<10 | 25 | 50>(25);
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitted, setSubmitted] = useState(false);

  const check = (over: Partial<Parameters<typeof validateForm>[0]> = {}) => {
    const e = validateForm({ origin, destination, departure, loadLb, interval, ...over });
    setErrors(e);
    return e;
  };

  const submit = (ev: React.FormEvent) => {
    ev.preventDefault();
    setSubmitted(true);
    const e = check();
    if (Object.keys(e).length || !origin || !destination) return;
    onSubmit({ origin, destination, departure_time: new Date(departure).toISOString(), load_lb: Number(loadLb), checkpoint_interval_miles: interval });
  };
  const live = (over: Parameters<typeof check>[0]) => { if (submitted) check(over); };

  return (
    <form className="panel" onSubmit={submit} noValidate aria-label="Trip planner">
      <h2>Plan a trip</h2>
      <LocationInput id="origin" label="Origin" value={origin} error={errors.origin}
        onChange={(p) => { setOrigin(p); live({ origin: p }); }} />
      <LocationInput id="destination" label="Destination" value={destination} error={errors.destination}
        onChange={(p) => { setDestination(p); live({ destination: p }); }} />
      <div className="row">
        <div className="field">
          <label htmlFor="departure">Departure</label>
          <input id="departure" type="datetime-local" value={departure} aria-invalid={!!errors.departure}
            onChange={(e) => { setDeparture(e.target.value); live({ departure: e.target.value }); }} />
          {errors.departure && <p className="field-error" role="alert">{errors.departure}</p>}
        </div>
        <div className="field">
          <label htmlFor="load">Load (lb)</label>
          <input id="load" type="number" inputMode="numeric" min={0} max={200000} step={500} value={loadLb} aria-invalid={!!errors.loadLb}
            onChange={(e) => { setLoadLb(e.target.value); live({ loadLb: e.target.value }); }} />
          {errors.loadLb && <p className="field-error" role="alert">{errors.loadLb}</p>}
        </div>
      </div>
      <fieldset className="field seg">
        <legend>Weather checkpoint every</legend>
        <div role="radiogroup" className="seg-row">
          {([10, 25, 50] as const).map((n) => (
            <label key={n} className={interval === n ? "on" : ""}>
              <input type="radio" name="interval" checked={interval === n} onChange={() => setIntervalMi(n)} /> {n} mi
            </label>
          ))}
        </div>
      </fieldset>
      <button className="primary" type="submit" disabled={loading}>{loading ? "Analyzing route weather…" : "Analyze routes"}</button>
    </form>
  );
}
