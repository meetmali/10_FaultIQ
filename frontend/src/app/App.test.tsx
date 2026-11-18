import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

function mockHealth(demoMode: boolean) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        status: "ok",
        service: "api",
        api_version: "0.1.0",
        environment: "production",
        demo_mode: demoMode,
        timestamp: "2026-11-05T00:00:00Z",
      }),
      { status: 200 },
    ),
  );
}

describe("App", () => {
  it("always shows the decision-support disclaimer", () => {
    vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {}));
    render(<App />);
    expect(screen.getByRole("contentinfo")).toHaveTextContent(
      /decision support only.*not a substitute for a qualified hvac technician/i,
    );
  });

  it("calls the API on the same origin", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {}));
    render(<App />);
    expect(fetchSpy.mock.calls[0]?.[0]).toBe("/api/v1/health");
  });

  it("shows the demo banner when the API is in demo mode", async () => {
    mockHealth(true);
    render(<App />);
    expect(await screen.findByRole("note", { name: /public demo notice/i })).toHaveTextContent(
      /sample data/i,
    );
  });

  it("hides the demo banner outside demo mode", async () => {
    mockHealth(false);
    render(<App />);
    await screen.findByText(/api online/i);
    expect(screen.queryByRole("note", { name: /public demo notice/i })).not.toBeInTheDocument();
  });
});
