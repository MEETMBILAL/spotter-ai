import { useState } from "react";
import type { Place } from "../api/types";
import { useGeocode } from "../hooks/useGeocode";

interface Props { id: string; label: string; value: Place | null; onChange: (p: Place | null) => void; error?: string }

export default function LocationInput({ id, label, value, onChange, error }: Props) {
  const [text, setText] = useState(value?.label ?? "");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const { results, loading, error: searchError } = useGeocode(text, open && value === null);
  const listId = `${id}-list`;

  const pick = (i: number) => {
    const r = results[i];
    if (!r) return;
    setText(r.label); setOpen(false); setActive(-1);
    onChange({ label: r.label, lon: r.lon, lat: r.lat });
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter" && open && active >= 0) { e.preventDefault(); pick(active); }
    else if (e.key === "Escape") setOpen(false);
  };

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="combo">
        <input
          id={id} type="text" autoComplete="off" placeholder="City, address or place"
          role="combobox" aria-expanded={open && results.length > 0} aria-controls={listId} aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${id}-opt-${active}` : undefined}
          aria-invalid={!!error} aria-describedby={error ? `${id}-err` : undefined}
          value={text} maxLength={200}
          onChange={(e) => { setText(e.target.value); if (value) onChange(null); setOpen(true); setActive(-1); }}
          onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} onKeyDown={onKey}
        />
        {value && <span className="tick" title="Location confirmed" aria-label="Location confirmed">✓</span>}
        {open && value === null && text.trim().length >= 3 && (
          <ul id={listId} role="listbox" className="suggest">
            {loading && <li className="muted" role="presentation">Searching…</li>}
            {!loading && searchError && <li className="err" role="presentation">{searchError}</li>}
            {!loading && !searchError && results.length === 0 && <li className="muted" role="presentation">No matches</li>}
            {results.map((r, i) => (
              <li key={r.id + i} id={`${id}-opt-${i}`} role="option" aria-selected={i === active}
                  className={i === active ? "active" : ""} onMouseDown={(e) => { e.preventDefault(); pick(i); }}>
                {r.label}
              </li>
            ))}
          </ul>
        )}
      </div>
      {error && <p id={`${id}-err`} className="field-error" role="alert">{error}</p>}
    </div>
  );
}
