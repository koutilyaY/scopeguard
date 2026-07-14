import { describe, expect, it } from "vitest";

import { formatMinor, formatMinutes } from "./api";

describe("formatMinor", () => {
  it("formats USD minor units", () => {
    expect(formatMinor(608000, "USD")).toBe("$6,080.00");
  });
  it("shows an em dash for unavailable value", () => {
    expect(formatMinor(null, "USD")).toBe("—");
  });
  it("defaults to USD when currency is null", () => {
    expect(formatMinor(10000, null)).toBe("$100.00");
  });
});

describe("formatMinutes", () => {
  it("formats whole hours", () => {
    expect(formatMinutes(120)).toBe("2h");
  });
  it("formats hours and minutes", () => {
    expect(formatMinutes(150)).toBe("2h 30m");
  });
});
