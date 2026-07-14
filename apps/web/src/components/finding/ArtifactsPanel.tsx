"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useMe } from "@/lib/hooks";
import type { FindingDetail } from "@/lib/types";

const DECISION_ROLES = ["organization_admin", "finance_manager", "project_manager", "reviewer"];
const ARTIFACT_TYPES = [
  { value: "internal_review_summary", label: "Internal review summary" },
  { value: "change_order_draft", label: "Change-order draft" },
  { value: "invoice_narrative", label: "Invoice narrative" },
  { value: "clarification_email", label: "Clarification email" },
];
const APPROVED_STATUSES = ["approved_for_followup", "approved_for_billing"];

export function ArtifactsPanel({ finding }: { finding: FindingDetail }) {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const [artifactType, setArtifactType] = useState("internal_review_summary");
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canGenerate = me && DECISION_ROLES.includes(me.role);
  const approved = APPROVED_STATUSES.includes(finding.review_status);

  async function generate() {
    setBusy(true);
    setError(null);
    setContent(null);
    try {
      const res = await api.post<{ content: string }>("/generated-artifacts", {
        finding_id: finding.id,
        artifact_type: artifactType,
      });
      setContent(res.content);
      qc.invalidateQueries({ queryKey: ["finding", finding.id] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card p-4">
      <h2 className="mb-2 font-medium">Generate draft artifact</h2>
      {!approved ? (
        <p className="text-sm text-slate-500">
          Approve this finding for follow-up or billing before generating any external-facing draft.
        </p>
      ) : !canGenerate ? (
        <p className="text-sm text-slate-500">Your role cannot generate artifacts.</p>
      ) : (
        <div className="space-y-3">
          <select
            className="input"
            value={artifactType}
            onChange={(e) => setArtifactType(e.target.value)}
            aria-label="Artifact type"
          >
            {ARTIFACT_TYPES.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
          <button className="btn-primary w-full" onClick={generate} disabled={busy}>
            {busy ? "Generating…" : "Generate draft"}
          </button>
          <p className="text-xs text-slate-500">
            Drafts are never sent automatically. No email is sent and no invoice is created.
          </p>
        </div>
      )}
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {content && (
        <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs text-slate-700">
          {content}
        </pre>
      )}
      {finding.artifacts.length > 0 && (
        <div className="mt-3 border-t border-slate-100 pt-2 text-xs text-slate-500">
          {finding.artifacts.length} artifact(s) generated for this finding.
        </div>
      )}
    </div>
  );
}
