import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { deviationTone } from "../../lib/deviation";
import { CutawaySchematic } from "./CutawaySchematic";
import { IsometricRtu } from "./IsometricRtu";
import { unitState } from "./components";

describe("isometric rooftop unit", () => {
  it("names the part at fault in text, not only in colour", () => {
    render(<IsometricRtu state="fault" component="condenser" title="RTU-1, running. Problem area: outdoor coil." />);
    expect(screen.getByRole("img", { name: /Problem area: outdoor coil/ })).toBeInTheDocument();
    expect(screen.getByText("Outdoor (condenser) coil")).toBeInTheDocument();
  });

  it("stays still and unlabelled when off or as a thumbnail", () => {
    const { container } = render(<IsometricRtu state="off" title="RTU-2, off." />);
    expect(container.querySelector(".fq-spin, .fq-flow")).toBeNull();
    const thumb = render(<IsometricRtu state="fault" component="oa_damper" variant="thumb" title="RTU-3" />);
    expect(thumb.container.querySelector("text")).toBeNull();
  });

  it("maps equipment status to an illustration state", () => {
    expect(unitState("fault")).toBe("fault");
    expect(unitState("abnormal")).toBe("unclear");
    expect(unitState("no_data")).toBe("off");
  });
});

describe("cutaway schematic", () => {
  it("shows each reading as text where the sensor is", () => {
    render(
      <CutawaySchematic
        title="Schematic at 02 Aug 2018, 15:00"
        readings={{ refg_disc_pres: { text: "1,892 kPa", tone: "fault", note: "+5.8 typical errors" } }}
        fanOn compressorOn damper={0.2} highlight="condenser"
      />,
    );
    expect(screen.getByText("1,892 kPa")).toBeInTheDocument();
    expect(screen.getByText("DISCHARGE")).toBeInTheDocument();
  });
});

describe("deviation from normal", () => {
  const band = { label: "x", unit: "errors", kind: "residual" as const, values: [], normal_low: -1, normal_high: 1 };
  it("grades inside, slightly outside and well outside the fault-free band", () => {
    expect(deviationTone(0.5, band)).toBe("ok");
    expect(deviationTone(2.5, band)).toBe("warn");
    expect(deviationTone(5.8, band)).toBe("fault");
    expect(deviationTone(null, band)).toBe("idle");
    expect(deviationTone(1, undefined)).toBe("idle");
  });
});
