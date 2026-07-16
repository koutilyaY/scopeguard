import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ReviewRun } from "@/lib/types";

const run = (overrides: Partial<ReviewRun> = {}): ReviewRun => ({
  id: "run-1",
  project_id: "p1",
  billing_period_start: "2025-06-01",
  billing_period_end: "2025-06-30",
  status: "completed",
  model_name: "fake",
  prompt_version: "v1",
  started_at: null,
  completed_at: null,
  failure_reason: null,
  stats: { findings_created: 2 },
  created_at: "2025-07-01T00:00:00Z",
  ...overrides,
});

const state = { runs: [run()] };

vi.mock("@/lib/hooks", () => ({
  useReviewRuns: () => ({
    data: { items: state.runs, total: state.runs.length, page: 1, page_size: 50 },
    isLoading: false,
  }),
  useMe: () => ({ data: { role: "organization_admin" } }),
  useReviewRun: () => ({ data: undefined }),
}));

const { ReviewTab } = await import("./ReviewTab");

function renderTab() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ReviewTab projectId="p1" />
    </QueryClientProvider>,
  );
}

describe("ReviewTab failure surfacing", () => {
  it("shows no failure alert for a clean run", () => {
    state.runs = [run()];
    renderTab();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("surfaces failure_reason to the user when a run partially failed", () => {
    // Regression: the run status badge alone left users with no idea WHY analysis was
    // incomplete. Background-job failures must be user-visible.
    state.runs = [
      run({
        status: "completed_with_errors",
        failure_reason:
          "group work_item:DE-106: Ollama unreachable or failing at http://ollama:11434",
      }),
    ];
    renderTab();
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/findings may be incomplete/i);
    expect(alert).toHaveTextContent(/Ollama unreachable/i);
  });
});
