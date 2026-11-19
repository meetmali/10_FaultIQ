import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../services/api";
import { renderRoute } from "../test/render";

vi.mock("../services/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../services/api")>();
  return {
    ...actual,
    getHealth: vi.fn(),
    getEquipmentOverview: vi.fn(),
    listSites: vi.fn(),
    listFaultEvents: vi.fn(),
    summariseFaultEvents: vi.fn(),
    listFaultLibrary: vi.fn(),
  };
});

const health = (demo: boolean) => ({
  status: "ok", service: "api", api_version: "0.1.0", environment: "test", demo_mode: demo, timestamp: "2026-11-19T00:00:00Z",
});
const empty = { items: [], page: 1, page_size: 20, total: 0 };

beforeEach(() => {
  vi.mocked(api.getHealth).mockResolvedValue(health(false));
  vi.mocked(api.listSites).mockResolvedValue([]);
  vi.mocked(api.listFaultEvents).mockResolvedValue(empty);
  vi.mocked(api.summariseFaultEvents).mockResolvedValue({ items: [], events: 0, hours: 0 });
  vi.mocked(api.listFaultLibrary).mockResolvedValue({ review_status: "unreviewed", sources: [], items: [] });
});

describe("dashboard states", () => {
  it("explains what to do when there is no equipment yet", async () => {
    vi.mocked(api.getEquipmentOverview).mockResolvedValue(empty);
    renderRoute("/");
    expect(await screen.findByText(/No equipment yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Analyse new data/ })).toBeInTheDocument();
  });

  it("shows an error with a retry instead of a blank page", async () => {
    vi.mocked(api.getEquipmentOverview).mockRejectedValue(new api.ApiError(500, { code: "internal_error", detail: "An unexpected error occurred." }));
    renderRoute("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("An unexpected error occurred.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("marks sample data and hides uploads in demo mode", async () => {
    vi.mocked(api.getHealth).mockResolvedValue(health(true));
    vi.mocked(api.getEquipmentOverview).mockResolvedValue({
      ...empty,
      total: 1,
      items: [{
        id: "e1", name: "RTU-1", site: "Demo", status: "fault", latest_analysis_id: "a1", latest_analysis_status: "succeeded",
        latest_analysis_at: "2026-11-19T00:00:00Z", hours_scored: 100, hours_alarmed: 20, fault_events: 2, other_events: 0,
        top_fault: "condenser_fouling",
      }],
    });
    renderRoute("/");
    expect(await screen.findByRole("note", { name: "Public demo notice" })).toBeInTheDocument();
    expect((await screen.findAllByText("sample data")).length).toBeGreaterThan(0);
    await waitFor(() => expect(screen.queryByRole("button", { name: /Analyse new data/ })).toBeNull());
    expect(screen.getByRole("link", { name: "RTU-1" })).toHaveAttribute("href", "/equipment/e1");
  });
});

describe("navigation", () => {
  it("shows a helpful page for unknown routes", async () => {
    renderRoute("/nowhere");
    expect(await screen.findByText("Page not found")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to the dashboard" })).toHaveAttribute("href", "/");
  });
});
