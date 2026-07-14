"use client";

import Link from "next/link";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useMe, useReviewRun, useReviewRuns } from "@/lib/hooks";
import { Badge, LoadingState } from "@/components/ui";
import type { ReviewRun } from "@/lib/types";

const DECISION_ROLES = ["organization_admin", "finance_manager", "project_manager", "reviewer"];

export function ReviewTab({ projectId }: { projectId: string }) {
  const { data, isLoading } = useReviewRuns(projectId);
  const { data: me } = useMe();
  const qc = useQueryClient();
  const canReview = me && DECISION_ROLES.includes(me.role);

  const [start, setStart] = useState("2025-06-01");
  const [end, setEnd] = useState("2025-06-30");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // poll the just-created run until it finishes
  const { data: activeRun } = useReviewRun(activeRunId ?? "", !!activeRunId);
  const runDone =
    activeRun && ["completed", "completed_with_errors", "failed"].includes(activeRun.status);
  if (activeRunId && runDone) {
    setActiveRunId(null);
    qc.invalidateQueries({ queryKey: ["review-runs", projectId] });
  }

  async function runReview() {
    setError(null);
    try {
      const run = await api.post<ReviewRun>("/review-runs", {
        project_id: projectId,
        billing_period_start: start,
        billing_period_end: end,
      });
      setActiveRunId(run.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start review.");
    }
  }

  if (isLoading) return <LoadingState />;

  return (
    <div className="space-y-4">
      {canReview && (
        <div className="card space-y-3 p-4">
          <h3 className="font-medium">Run a billing-period review</h3>
          <p className="text-xs text-slate-500">
            Did we perform potentially out-of-scope work during this period, with enough evidence to
            review it? The review never invoices anyone — it produces findings for human review.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="label" htmlFor="start">
                Period start
              </label>
              <input
                id="start"
                type="date"
                className="input"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="end">
                Period end
              </label>
              <input
                id="end"
                type="date"
                className="input"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
            <button className="btn-primary" onClick={runReview} disabled={!!activeRunId}>
              {activeRunId ? "Running…" : "Run review"}
            </button>
          </div>
          {activeRunId && activeRun && (
            <p className="text-sm text-brand-700" role="status">
              Review status: {activeRun.status}…
            </p>
          )}
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>
      )}

      {!data || data.items.length === 0 ? (
        <p className="text-sm text-slate-500">No reviews have been run for this project yet.</p>
      ) : (
        <div className="card divide-y divide-slate-100">
          {data.items.map((r) => (
            <div key={r.id} className="flex items-center justify-between p-3 text-sm">
              <div>
                <p className="font-medium">
                  {r.billing_period_start} → {r.billing_period_end}
                </p>
                <p className="text-slate-500">
                  {r.stats?.findings_created ?? 0} finding(s)
                  {r.model_name ? ` · ${r.model_name}` : ""}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <Badge value={r.status} />
                <Link
                  className="text-brand-600 hover:underline"
                  href={`/findings?review_run_id=${r.id}`}
                >
                  View findings →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
