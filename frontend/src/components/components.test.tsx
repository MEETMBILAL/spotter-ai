import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { analysis, cp, heatmap, route } from "../test-fixtures";
import { CheckpointDetail, CheckpointList } from "./CheckpointPanel";
import HeatmapControls from "./HeatmapControls";
import RecommendationPanel from "./RecommendationPanel";
import RouteList from "./RouteList";

afterEach(cleanup);

describe("RouteList", () => {
  it("shows recommended/blocked status and selects a route on click", () => {
    const onSelect = vi.fn();
    const routes = [route("route-1", { ranking: { rank: 1, eligible: true, ineligible_reason: null, decided_by: null, recommended: true } }),
      route("route-2", { ranking: { rank: null, eligible: false, ineligible_reason: "Contains 12.0 No Travel miles", decided_by: null, recommended: false },
        summary: { ...route("x").summary, has_no_travel: true } })];
    render(<RouteList routes={routes} selectedId="route-1" onSelect={onSelect} />);
    expect(screen.getByText("Recommended")).toBeTruthy();
    expect(screen.getByText("No Travel")).toBeTruthy();
    expect(screen.getByText(/Not eligible: Contains 12.0 No Travel/)).toBeTruthy();
    const radios = screen.getAllByRole("radio");
    expect(radios[0].getAttribute("aria-checked")).toBe("true");
    fireEvent.click(radios[1]);
    expect(onSelect).toHaveBeenCalledWith("route-2");
  });
});

describe("RecommendationPanel", () => {
  it("states 'No Safe Route Available' when every route is blocked", () => {
    const d = analysis({ recommendation: { status: "no_safe_route", message: "No Safe Route Available", route_id: null, reasons: [], warnings: [] } });
    render(<RecommendationPanel data={d} />);
    expect(screen.getAllByText("No Safe Route Available").length).toBeGreaterThan(0);
  });
  it("shows partial-data and truck-routing warnings", () => {
    const d = analysis({ recommendation: { ...analysis().recommendation, status: "recommended_partial_data", warnings: ["12.0 mi has no weather forecast"] }, warnings: ["not truck-specific"] });
    render(<RecommendationPanel data={d} />);
    expect(screen.getByText(/12.0 mi has no weather forecast/)).toBeTruthy();
    expect(screen.getByText(/not truck-specific/)).toBeTruthy();
  });
});

describe("Checkpoint panels", () => {
  it("presents unavailable weather as Unavailable/Unknown, never as zero or Low", () => {
    const unknown = cp(2, { weather: { status: "unavailable", reason: "forecast_not_covered", wind_mph: null, rain_in_hr: null, snow_in_hr: null },
      risk: { wind: { level: null, label: "Unknown" }, rain: { level: null, label: "Unknown" }, snow: { level: null, label: "Unknown" }, final: { level: null, label: "Unknown" }, complete: false, load_override_applied: false } });
    render(<CheckpointDetail cp={unknown} onClose={() => {}} />);
    expect(screen.getAllByText("Unavailable").length).toBe(3);
    expect(screen.getAllByText("Unknown").length).toBe(4);
    expect(screen.getByText(/outside the forecast range/)).toBeTruthy();
  });
  it("shows load override note and closes", () => {
    const onClose = vi.fn();
    const c = cp(1); c.risk.final = { level: 3, label: "Severe" }; c.risk.load_override_applied = true;
    render(<CheckpointDetail cp={c} onClose={onClose} />);
    expect(screen.getByText(/raised by load rule/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Close checkpoint details"));
    expect(onClose).toHaveBeenCalled();
  });
  it("lists checkpoints as keyboard-focusable buttons and selects one", () => {
    const onSelect = vi.fn();
    render(<CheckpointList route={route("route-1")} selected={null} onSelect={onSelect} />);
    const list = screen.getByRole("list");
    fireEvent.click(within(list).getAllByRole("button")[1]);
    expect(onSelect).toHaveBeenCalledWith(1);
  });
});

describe("HeatmapControls", () => {
  const base = { enabled: true, onToggle: () => {}, hour: 0, metric: "risk" as const, onMetric: () => {}, onRetry: () => {} };
  it("slider covers 0-48 and reports changes", () => {
    const onHour = vi.fn();
    render(<HeatmapControls {...base} state={{ status: "done", data: heatmap() }} onHour={onHour} />);
    const s = screen.getByLabelText("Forecast hour") as HTMLInputElement;
    expect([s.min, s.max]).toEqual(["0", "48"]);
    fireEvent.change(s, { target: { value: "48" } });
    expect(onHour).toHaveBeenCalledWith(48);
  });
  it("flags hours without forecast, and the loading/error states", () => {
    const { rerender } = render(<HeatmapControls {...base} hour={45} onHour={() => {}} state={{ status: "done", data: heatmap() }} />);
    expect(screen.getByText(/No forecast data for this hour/)).toBeTruthy();
    rerender(<HeatmapControls {...base} onHour={() => {}} state={{ status: "loading" }} />);
    expect(screen.getByRole("status").textContent).toMatch(/49 hourly/);
    const retry = vi.fn();
    rerender(<HeatmapControls {...base} onHour={() => {}} onRetry={retry} state={{ status: "error", error: "boom" }} />);
    fireEvent.click(screen.getByText("Retry"));
    expect(retry).toHaveBeenCalled();
  });
});
