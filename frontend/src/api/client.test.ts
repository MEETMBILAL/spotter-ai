import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, analyzeTrip, fetchHeatmap, geocode } from "./client";
import { analysis, heatmap } from "../test-fixtures";
import type { TripRequest } from "./types";

const req: TripRequest = { origin: { label: "A", lon: -100, lat: 40 }, destination: { label: "B", lon: -96, lat: 40 }, departure_time: "2026-11-12T14:00:00Z", load_lb: 40000, checkpoint_interval_miles: 25 };
const reply = (body: unknown, status = 200) => vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body });
afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("posts the trip and returns a validated analysis", async () => {
    const f = reply(analysis()); vi.stubGlobal("fetch", f);
    const d = await analyzeTrip(req);
    expect(d.routes).toHaveLength(2);
    expect(f.mock.calls[0][0]).toBe("/api/analyze");
    expect(JSON.parse(f.mock.calls[0][1].body)).toMatchObject({ load_lb: 40000, checkpoint_interval_miles: 25 });
  });
  it("maps backend errors (with field details) to ApiError", async () => {
    vi.stubGlobal("fetch", reply({ error: { code: "invalid_request", message: "The request is invalid.", details: { load_lb: ["Too big"] } } }, 400));
    await expect(analyzeTrip(req)).rejects.toMatchObject({ code: "invalid_request", status: 400, message: expect.stringContaining("load_lb: Too big") });
  });
  it("reports network failure without crashing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fail")));
    await expect(analyzeTrip(req)).rejects.toMatchObject({ code: "network" });
  });
  it("rejects structurally invalid success responses", async () => {
    vi.stubGlobal("fetch", reply({ hello: "world" }));
    await expect(analyzeTrip(req)).rejects.toBeInstanceOf(ApiError);
    vi.stubGlobal("fetch", reply({ ...heatmap(), frames: [] }));
    await expect(fetchHeatmap(req, 0)).rejects.toMatchObject({ code: "invalid_response" });
  });
  it("handles non-JSON error bodies", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 502, json: async () => { throw new Error("html"); } }));
    await expect(analyzeTrip(req)).rejects.toMatchObject({ status: 502, message: expect.stringContaining("502") });
  });
  it("geocode encodes the query and unwraps results", async () => {
    const f = reply({ results: [{ id: "1", name: "X", label: "X, Y", lon: 1, lat: 2 }] }); vi.stubGlobal("fetch", f);
    expect(await geocode("St. Louis, MO")).toHaveLength(1);
    expect(f.mock.calls[0][0]).toBe("/api/geocode?q=St.%20Louis%2C%20MO");
  });
  it("heatmap request includes the route index", async () => {
    const f = reply(heatmap()); vi.stubGlobal("fetch", f);
    await fetchHeatmap(req, 2);
    expect(JSON.parse(f.mock.calls[0][1].body).route_index).toBe(2);
  });
});
