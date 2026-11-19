import { describe, expect, it } from "vitest";

import { formatConfidence, formatDataTime, formatDateTime, formatValue } from "./format";
import { backLink } from "./links";

describe("formatting", () => {
  it("never shows a model as certain or a class as impossible", () => {
    expect(formatConfidence(0.9996)).toBe("over 99%");
    expect(formatConfidence(0)).toBe("under 1%");
    expect(formatConfidence(0.41)).toBe("41%");
  });

  it("shows data times as recorded, matching the explanation text, and system times as UTC", () => {
    expect(formatDataTime("2018-08-02T15:00:00+00:00")).toBe("02 Aug 2018, 15:00");
    expect(formatDataTime("2018-09-07T01:00:00+00:00")).toContain("Sep"); // not "Sept"
    expect(formatDateTime("2026-11-19T14:37:00Z")).toBe("19 Nov 2026, 14:37 UTC");
  });

  it("labels values with their units", () => {
    expect(formatValue(1892.4, "kPa")).toBe("1,892 kPa");
    expect(formatValue(10.94, "degC")).toBe("10.9 °C");
    expect(formatValue(0.5, "share")).toBe("50%");
  });
});

describe("backLink", () => {
  it("only honours internal diagnosis links", () => {
    const ok = "/equipment/01a1f43d-b485-743e-9277-be60bbd5ce44?analysis=01a1f43d&event=event-4";
    expect(backLink(ok)).toBe(ok);
    for (const bad of ["https://evil.example", "//evil.example/equipment/1", "javascript:alert(1)", "/library", null]) {
      expect(backLink(bad)).toBeNull();
    }
  });
});
