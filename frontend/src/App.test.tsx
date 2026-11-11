import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

vi.mock("./components/MapView", () => ({ default: () => <div data-testid="map" /> }));
import App from "./App";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("blocks submission with field errors and makes no API call", async () => {
  const f = vi.fn(); vi.stubGlobal("fetch", f);
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: /analyze routes/i }));
  expect(screen.getByText(/Choose an origin/)).toBeTruthy();
  expect(screen.getByText(/Choose a destination/)).toBeTruthy();
  expect(f).not.toHaveBeenCalled();
  await waitFor(() => expect(screen.getByTestId("map")).toBeTruthy());
});

it("shows an idle explanation (no fabricated results) before any analysis", () => {
  render(<App />);
  expect(screen.getByText(/nothing is simulated/i)).toBeTruthy();
});
