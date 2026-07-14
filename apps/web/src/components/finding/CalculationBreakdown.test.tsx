import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CalculationBreakdown } from "./CalculationBreakdown";

const calculation = {
  method: "eligible minutes / 60 × applicable verified hourly rate (ROUND_HALF_UP)",
  currency: "USD",
  total_minor: 608000,
  entries: [
    {
      time_entry_id: "t1",
      employee: "Priya Raman",
      role: "Data Engineer",
      date: "2025-06-05",
      minutes: 360,
      rate_minor: 17500,
      value_minor: 105000,
    },
  ],
  missing_rates_for_roles: [],
};

const evidence = {
  label: "Evidence completeness",
  disclaimer: "Deterministic completeness of available evidence. Not a legal probability.",
  score: 0.95,
  components: [
    { component: "verified_contract_clause", present: true, weight: 0.25, contribution: 0.25 },
    { component: "written_authorization", present: false, weight: 0.05, contribution: 0 },
  ],
};

describe("CalculationBreakdown", () => {
  it("renders the deterministic total and per-entry rows", () => {
    render(<CalculationBreakdown calculation={calculation} evidence={evidence} />);
    expect(screen.getByText(/Total:\s*\$6,080\.00/)).toBeInTheDocument();
    expect(screen.getByText("Priya Raman")).toBeInTheDocument();
    expect(screen.getByText(/never by the language model/i)).toBeInTheDocument();
  });

  it("shows evidence completeness with the non-legal disclaimer", () => {
    render(<CalculationBreakdown calculation={calculation} evidence={evidence} />);
    expect(screen.getByText(/Evidence completeness: 95%/)).toBeInTheDocument();
    expect(screen.getByText(/Not a legal probability/)).toBeInTheDocument();
  });

  it("renders duplicate groups when present", () => {
    const dup = {
      duplicate_groups: [
        { kind: "exact", explanation: "Identical entry excluded from totals." },
      ],
    };
    render(<CalculationBreakdown calculation={dup} evidence={null} />);
    expect(screen.getByText(/exact duplicate:/)).toBeInTheDocument();
  });

  it("shows value unavailable for missing rates", () => {
    const missing = {
      method: "x",
      currency: "USD",
      total_minor: null,
      entries: [],
      missing_rates_for_roles: ["Astrologer"],
    };
    render(<CalculationBreakdown calculation={missing} evidence={null} />);
    expect(screen.getByText(/value unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/No verified rate for: Astrologer/)).toBeInTheDocument();
  });
});
