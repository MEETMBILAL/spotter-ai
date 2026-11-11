import { describe, expect, it } from "vitest";
import { validateForm, type FormValues } from "./validate";

const now = new Date("2026-11-10T12:00:00Z");
const ok: FormValues = { origin: { label: "A", lon: -100, lat: 40 }, destination: { label: "B", lon: -90, lat: 41 }, departure: "2026-11-11T08:00", loadLb: "40000", interval: 25 };

describe("validateForm", () => {
  it("accepts a valid form", () => expect(validateForm(ok, now)).toEqual({}));
  it("requires confirmed locations", () => {
    const e = validateForm({ ...ok, origin: null, destination: null }, now);
    expect(e.origin).toBeTruthy(); expect(e.destination).toBeTruthy();
  });
  it("rejects identical locations", () => expect(validateForm({ ...ok, destination: { ...ok.origin! } }, now).destination).toMatch(/differ/));
  it.each(["", "abc", "-1", "200001"])("rejects load %p", (v) => expect(validateForm({ ...ok, loadLb: v }, now).loadLb).toBeTruthy());
  it.each(["0", "200000"])("accepts boundary load %p", (v) => expect(validateForm({ ...ok, loadLb: v }, now).loadLb).toBeUndefined());
  it("rejects departures outside the forecast window", () => {
    expect(validateForm({ ...ok, departure: "2026-11-01T08:00" }, now).departure).toBeTruthy();
    expect(validateForm({ ...ok, departure: "2026-12-30T08:00" }, now).departure).toBeTruthy();
    expect(validateForm({ ...ok, departure: "" }, now).departure).toBeTruthy();
  });
});
