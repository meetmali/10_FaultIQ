import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KindBadge, ReviewBadge, StatusBadge } from "./Badges";

describe("status badges", () => {
  // Section 11: status is never conveyed by colour alone.
  it.each([
    ["fault", "Fault detected"],
    ["abnormal", "Abnormal, unexplained"],
    ["normal", "Normal"],
    ["analysis_failed", "Analysis failed"],
    ["no_data", "No data yet"],
  ])("shows %s as text with an icon", (status, label) => {
    const { container } = render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(container.querySelector("svg[aria-hidden='true']")).not.toBeNull();
  });

  it("names event kinds and review outcomes in plain words", () => {
    render(
      <>
        <KindBadge kind="no_supported_fault" />
        <ReviewBadge status="confirmed" />
      </>,
    );
    expect(screen.getByText("Unrecognised abnormality")).toHaveAttribute("title", expect.stringContaining("none of the supported faults"));
    expect(screen.getByText("Confirmed on site")).toBeInTheDocument();
  });
});
