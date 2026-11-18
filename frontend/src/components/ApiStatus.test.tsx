import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiStatus } from "./ApiStatus";

describe("ApiStatus", () => {
  it("shows a loading state", () => {
    render(<ApiStatus state={{ kind: "loading" }} />);
    expect(screen.getByRole("status")).toHaveTextContent(/checking api/i);
  });

  it("shows the version when the API is healthy", () => {
    render(
      <ApiStatus
        state={{
          kind: "ok",
          health: {
            status: "ok",
            service: "api",
            api_version: "0.1.0",
            environment: "test",
            demo_mode: false,
            timestamp: "2026-11-05T00:00:00Z",
          },
        }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("version 0.1.0");
  });

  it("shows an error state when the API is unreachable", () => {
    render(<ApiStatus state={{ kind: "error", message: "Failed to fetch" }} />);
    expect(screen.getByRole("status")).toHaveTextContent(/api unreachable/i);
  });
});
