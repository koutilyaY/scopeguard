"use client";

import { useState } from "react";

import { useDecide, useMe } from "@/lib/hooks";
import type { FindingDetail } from "@/lib/types";

const DECISION_ROLES = ["organization_admin", "finance_manager", "project_manager", "reviewer"];

const ACTIONS: { value: string; label: string }[] = [
  { value: "approved_for_followup", label: "Approve for follow-up" },
  { value: "approved_for_billing", label: "Approve for billing" },
  { value: "rejected", label: "Reject" },
  { value: "already_resolved", label: "Mark already resolved" },
  { value: "needs_more_evidence", label: "Request more evidence" },
];

export function DecisionForm({ finding }: { finding: FindingDetail }) {
  const { data: me } = useMe();
  const decide = useDecide();
  const [newStatus, setNewStatus] = useState("");
  const [reason, setReason] = useState("");
  const canDecide = me && DECISION_ROLES.includes(me.role);

  if (!canDecide) {
    return (
      <div className="card p-4">
        <h2 className="mb-1 font-medium">Review decision</h2>
        <p className="text-sm text-slate-500">
          Your role ({me?.role.replace(/_/g, " ")}) has read-only access to findings.
        </p>
      </div>
    );
  }

  async function submit() {
    if (!newStatus || reason.trim().length < 5) return;
    await decide.mutateAsync({ finding_id: finding.id, new_status: newStatus, reason });
    setReason("");
    setNewStatus("");
  }

  return (
    <div className="card p-4">
      <h2 className="mb-2 font-medium">Review decision</h2>
      <p className="mb-3 text-xs text-slate-500">
        Current status: <strong>{finding.review_status.replace(/_/g, " ")}</strong>. A reason is
        required for every decision.
      </p>
      <div className="space-y-3">
        <div>
          <label className="label" htmlFor="action">
            Action
          </label>
          <select
            id="action"
            className="input"
            value={newStatus}
            onChange={(e) => setNewStatus(e.target.value)}
          >
            <option value="">Select…</option>
            {ACTIONS.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="reason">
            Reason
          </label>
          <textarea
            id="reason"
            className="input min-h-[80px]"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why are you making this decision?"
          />
        </div>
        {decide.isError && (
          <p className="text-sm text-red-600">
            {decide.error instanceof Error ? decide.error.message : "Decision failed."}
          </p>
        )}
        <button
          className="btn-primary w-full"
          onClick={submit}
          disabled={!newStatus || reason.trim().length < 5 || decide.isPending}
        >
          {decide.isPending ? "Recording…" : "Record decision"}
        </button>
      </div>
    </div>
  );
}
